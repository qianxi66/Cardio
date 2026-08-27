# -*- coding: utf-8 -*-

# This sample demonstrates handling intents from an Alexa skill using the Alexa Skills Kit SDK for Python.
# Please visit https://alexa.design/cookbook for additional examples on implementing slots, dialog management,
# session persistence, api calls, and more.
# This sample is built using the handler classes approach in skill builder.
import logging
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import json
import threading

import ask_sdk_core.utils as ask_utils
import requests
from flask import jsonify
from ask_sdk_core.dispatch_components import (
    AbstractExceptionHandler,
    AbstractRequestHandler,
)
from ask_sdk_model.ui.ask_for_permissions_consent_card import (
    AskForPermissionsConsentCard,
)
from ask_sdk_core.exceptions import SerializationException
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_core.skill_builder import CustomSkillBuilder
from ask_sdk_core.api_client import DefaultApiClient
from .app import app, db
from .db import Patient, User, ConversationLog, Summary
from .mongo import get_mongo_client
from .symptoms import symptom_descriptions
from .openai_utils import conversation as openai_conversation
from .config import auto_create_patient, mongodb_url, mongodb_client_kwargs
from pymongo import MongoClient

logger = app.logger


def _lookup_patient_by_alexa_identity(identity: str):
    raw = (identity or "").strip()
    if not raw:
        return None
    patient = Patient.query.filter(Patient.email.ilike(raw)).first()
    if patient is not None:
        return patient
    patient = Patient.query.filter_by(alexa_user_id=raw).first()
    if patient is not None:
        return patient
    if "@" in raw:
        local = raw.split("@", 1)[0].strip()
        if local:
            patient = Patient.query.filter_by(participant_id=local).first()
            if patient is not None:
                return patient
    return None


# Spoken by Alexa after ~8s of silence, before it listens for another ~8s. Deliberately
# short and not a repeat of the question: the previous wording ("Sorry, I didn't catch
# that") was wrong for the silence case, since the patient has not said anything, and
# re-reading the whole question spends the extra time talking rather than listening.
REPROMPT_TEXT = "I'm still here. Take your time."


# Size of the sliding window in days, counting today. Today is always sent in full as the
# live conversation; the HISTORY_WINDOW_DAYS - 1 days before it go in as background only.
# Set to 1 (today only) as of the 2026-08-19 team meeting: the clinical protocol has
# no rule that fires on a symptom repeating across days, and the agent follows the
# fixed question list regardless of prior answers, so earlier days added latency
# without changing what it asks. Raise this to re-enable the window for a study that
# does need cross-day context.
HISTORY_WINDOW_DAYS = 1
# Hard cap on that background block. Extra context costs latency, and Alexa drops the
# session if the endpoint takes longer than roughly 8 seconds (we have already seen two
# nginx 499s from exactly that). If the window is bigger than this, the oldest lines go.
HISTORY_MAX_CHARS = 4000


def _today_start_utc():
    """Naive-UTC timestamp of today's 00:00 Eastern, matching how logs are stored."""
    now_et = datetime.now(ZoneInfo("America/New_York"))
    return (
        now_et.replace(hour=0, minute=0, second=0, microsecond=0)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )


# Symptoms the daily check-in is expected to cover, taken from the same table the
# extraction uses so the two can't drift apart.
CONVERSATION_SYMPTOMS = [
    key
    for key, meta in symptom_descriptions.items()
    if meta.get("source") == "conversation"
]


def _todays_questions_are_done(patient_id):
    """Whether every symptom was covered in today's check-in.

    Reads the Summary row that process_patient_summary() writes when a session ends;
    state 0 means the symptom was never discussed. Note chain_of_thoughts is not usable
    for this: the Cardio prompt no longer emits the checklist, so the parse always falls
    back and stores "not discussed" for everything.

    Summary.date is bucketed to Eastern midnight as a naive value, which is a different
    convention from ConversationLog.date (naive UTC), so _today_start_utc() must not be
    reused here -- doing so silently matched nothing.

    Returns False when there is no row yet, which is the safe default: it makes the skill
    offer to carry on rather than assume a check-in it cannot see was finished.
    """
    day_start = datetime.now(ZoneInfo("America/New_York")).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=None
    )
    summary = (
        Summary.query.filter_by(patient_id=patient_id)
        .filter(Summary.date >= day_start)
        .filter(Summary.date < day_start + timedelta(days=1))
        .order_by(Summary.date.desc())
        .first()
    )
    if summary is None:
        return False
    return all(
        (getattr(summary, f"{key}_state", 0) or 0) != 0 for key in CONVERSATION_SYMPTOMS
    )


def _prior_days_context(patient_id, day_start_utc):
    """Compact, date-stamped transcript of the days before today.

    Returned as text for a system message rather than as extra entries in the chat
    messages list: replaying old turns as real turns is what made the skill pick up an
    unfinished question from weeks earlier and ask it as if it were today's.
    """
    window_start = day_start_utc - timedelta(days=HISTORY_WINDOW_DAYS - 1)
    # with_entities keeps these as plain row tuples instead of ORM instances. They are only
    # ever read as text, and every ORM instance loaded here would be added to the session's
    # identity map that gets walked again at request teardown.
    rows = (
        ConversationLog.query.filter_by(patient_id=patient_id)
        .filter(ConversationLog.date >= window_start)
        .filter(ConversationLog.date < day_start_utc)
        .order_by(ConversationLog.date.asc())
        .with_entities(ConversationLog.date, ConversationLog.role, ConversationLog.content)
        .all()
    )
    if not rows:
        return None
    lines = []
    for row_date, role, content in rows:
        speaker = "Patient" if role == "user" else "Assistant"
        text = (content or "").replace("\n", " ").strip()
        if not text:
            continue
        lines.append(f"[{row_date.strftime('%Y-%m-%d')}] {speaker}: {text}")
    if not lines:
        return None
    block = "\n".join(lines)
    if len(block) > HISTORY_MAX_CHARS:
        block = "(earlier lines omitted)\n" + block[-HISTORY_MAX_CHARS:]
    return block


def to_speech(handler_input, response):
    speak_output = response
    ask_output = REPROMPT_TEXT

    return (
        handler_input.response_builder.speak(speak_output)
        .ask(ask_output)
        .set_should_end_session(False)
        .response
    )

def getLastMessage(alexa_user_id: str):
    patient = _lookup_patient_by_alexa_identity(alexa_user_id)
    if patient is None:
        if auto_create_patient:
            participant_id = alexa_user_id.split("@")[0]
            patient = Patient(
                name="Alexa User",
                email=alexa_user_id if "@" in alexa_user_id else None,
                alexa_user_id=alexa_user_id,
                last_read_at=datetime.utcnow(),
                participant_id="AUTO_" + participant_id,
            )
            # allow all users to access this patient
            patient.users.extend(User.query.all())
            db.session.add(patient)
            db.session.commit()
        else:
            return {"message": "Patient not found."}, 404
    # Today only. Without this the launch handler replayed the last assistant message from
    # any point in history, so opening the skill could re-ask a question left unanswered
    # weeks ago; the model then saw only today's (empty) log and started over with the
    # greeting, giving the patient one stray turn before the real opening.
    messages = (
        ConversationLog.query.filter_by(patient_id=patient.id)
        .filter(ConversationLog.date >= _today_start_utc())
        .order_by(ConversationLog.date.asc())
        .all()
    )
    if len(messages) == 0:
        # create a new assistant message
        msg = "Hello, this is the Cardio research study chatbot assistant developed by Northeastern University Human-centered AI lab. We'll go through eight symptom-related questions, which will take about 2 to 5 minutes. Are you ready to start today's questions?"
        message = ConversationLog(
            patient_id=patient.id,
            role="assistant",
            chain_of_thoughts="",
            content=msg,
            date=datetime.utcnow(),
        )
        db.session.add(message)
        db.session.commit()
        from .apis import _invalidate_patient_related_cache
        _invalidate_patient_related_cache(patient.id)
        return {"message": "success", "last_message": message.as_dict()}
    messages = [message.as_dict() for message in messages]
    messages = [i for i in messages if i["role"] == "assistant"]
    return {"message": "success", "last_message": messages[-1]}


def _latest_field_value(db, collection_name, uid, field_name):
    doc = (
        db[collection_name]
        .find({"uid": uid})
        .sort("timestamp", -1)
        .limit(1)
    )
    result = next(doc, None)
    if result is None:
        return None
    return result.get(field_name)

@app.route("/session_end_hook/<alexa_user_id>", methods=["POST"])
def session_end_hook(alexa_user_id):
    with app.app_context():
        logger.info("session_end_hook")
        patient = _lookup_patient_by_alexa_identity(alexa_user_id)
        logger.info(f"patient: {patient}")
        if patient is None:
            return jsonify({"message": "patient not found"}), 404
        # Run the conversation symptom extraction so the dashboard summary is
        # updated when an Alexa session ends (imported lazily to avoid any
        # import-order coupling with apis).
        try:
            from .apis import process_patient_summary
            process_patient_summary(patient.id, datetime.utcnow())
            logger.info("session end hook: process_patient_summary done for patient_id=%s", patient.id)
        except Exception as e:
            logger.error(f"session_end_hook: process_patient_summary failed: {e}")
        return jsonify({"message": "success"})

def conversationEnded(alexa_user_id: str):
    try:
        # Launch session_end_hook in a new thread
        thread = threading.Thread(target=session_end_hook, args=(alexa_user_id,))
        thread.daemon = True  # Make thread daemon so it doesn't block program exit
        thread.start()
        return True
    except Exception as e:
        logger.error(f"Failed to end session: {e}")
        return False

def conversation(alexa_user_id: str, content: str):
    try:
        # get patient with alexa_user_id
        patient = _lookup_patient_by_alexa_identity(alexa_user_id)
        if patient is None:
            raise PatientNotFound(f"Patient not found for alexa_user_id: {alexa_user_id}")
        
        wearable_data = None
        if patient.participant_id:
            try:
                # Shared process-wide client: this ran on every single Alexa turn, and
                # building/closing a MongoClient each time churns its monitor threads.
                client = get_mongo_client()
                db2 = client["study_db"] if client is not None else None
                stress_value = _latest_field_value(
                    db2, "garmin_stress", patient.participant_id, "heart_rate"
                )
                steps_value = _latest_field_value(
                    db2, "garmin_steps", patient.participant_id, "total_steps"
                )
                hr_value = _latest_field_value(
                    db2, "garmin_hr", patient.participant_id, "heart_rate"
                )
                wearable_data = {
                    "today": {
                        "avg_stress": stress_value,
                        "max_stress": stress_value,
                        "avg_steps": steps_value,
                        "max_steps": steps_value,
                        "max_hr": hr_value,
                        "min_hr": hr_value,
                    }
                }
            except Exception as e:
                logger.warning("Wearable lookup failed: %s", e)

        
        # Create conversation log for user message
        log = ConversationLog(
            patient_id=patient.id,
            role="user",
            content=content,
            date=datetime.utcnow(),
        )
        db.session.add(log)
        db.session.commit()
        
        # Only feed TODAY's conversation to the model. The prompt assumes all
        # messages happen in the same day; mixing in prior days' logs (which may
        # use an older question format) makes the model drift off the required
        # output format and inflates latency toward Alexa's response timeout.
        _day_start_utc = _today_start_utc()
        prior_days_context = _prior_days_context(patient.id, _day_start_utc)
        conversation_logs = (
            ConversationLog.query.filter_by(patient_id=patient.id)
            .filter(ConversationLog.date >= _day_start_utc)
            .order_by(ConversationLog.date.asc())
            .all()
        )
        conversation_logs = [log.as_dict() for log in conversation_logs]
        conversation_logs = [
            {
                "content": log["content"]
                if log["role"] == "user"
                else (log.get("chain_of_thoughts") or "") + "==============\n" + log["content"],
                "role": log["role"],
            }
            for log in conversation_logs
        ]
        logger.info(f"conversation_logs: {conversation_logs}")
            
        assistant_message = openai_conversation(
            conversation_logs,
            wearable_data=wearable_data,
            prior_days_context=prior_days_context,
        )
        logger.info("Wearable data sent to LLM: %s", wearable_data)
        logger.info(f"assistant_message: {assistant_message}")
        try:
            chain_of_thoughts = assistant_message.split("==============")[0]
            assistant_message = assistant_message.split("==============")[1].strip(" \n")
        except IndexError:
            chain_of_thoughts = """blood_pressure: not discussed
chest_pain: not discussed
shortness_of_breath: not discussed
swelling: not discussed
dizziness: not discussed
palpitation: not discussed
fatigue: not discussed
weight: not discussed
weight_gain: not discussed
fainted: not discussed
misc: not discussed
"""
            pass
        log = ConversationLog(
            patient_id=patient.id,
            role="assistant",
            content=assistant_message,
            chain_of_thoughts=chain_of_thoughts,
            date=datetime.utcnow(),
        )
        db.session.add(log)
        db.session.commit()
        from .apis import _invalidate_patient_related_cache
        _invalidate_patient_related_cache(patient.id)
        return log.as_dict()
    except PatientNotFound as e:
        logger.error(f"Patient not found: {e}")
        raise
    except Exception as e:
        logger.error(f"Error in conversation: {e}")
        raise ConversationError(f"Error processing conversation: {e}")


class EmailPermissionDenied(Exception):
    pass

class PatientNotFound(Exception):
    pass

class ConversationError(Exception):
    pass

# Alexa userId -> (email, expires_at). The UPS lookup below is an outbound HTTPS call to
# Amazon on the critical path of *every* request, and the endpoint only has ~8 seconds
# before Alexa abandons the session (we have seen nginx 499s from exactly that). The
# address behind a given userId does not change during a session, so cache it.
_EMAIL_CACHE = {}
EMAIL_CACHE_TTL_SECONDS = 6 * 60 * 60


def get_customer_email(handler_input: HandlerInput) -> str:
    # Permission is re-checked on every request, before the cache is consulted, so a
    # patient who revokes email consent starts failing immediately instead of being
    # served from a warm entry.
    try:
        permissions = handler_input.request_envelope.context.system.user.permissions
        if not permissions or not permissions.consent_token:
            raise EmailPermissionDenied
    except Exception:
        raise EmailPermissionDenied

    try:
        user_id = handler_input.request_envelope.context.system.user.user_id
    except Exception:
        user_id = None

    if user_id:
        cached = _EMAIL_CACHE.get(user_id)
        if cached and cached[1] > time.time():
            return cached[0]

    try:
        ups_client = handler_input.service_client_factory.get_ups_service()
        result = ups_client.get_profile_email()
        if isinstance(result, str) and result:
            if user_id:
                _EMAIL_CACHE[user_id] = (result, time.time() + EMAIL_CACHE_TTL_SECONDS)
            return result
        raise EmailPermissionDenied
    except Exception as e:
        logger.warning("UPS email lookup failed: %s", e)
        raise EmailPermissionDenied


class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        logger.info("LaunchRequestHandler")
        logger.info(handler_input.request_envelope)
        last_message = getLastMessage(get_customer_email(handler_input))
        if isinstance(last_message, tuple) and last_message[1] == 404:
            speak_output = "We don't have a valid participant ID for you. Please contact the system administrator to create one."
            return to_speech(handler_input, speak_output)
        if last_message["message"] == "success":
            speak_output = last_message["last_message"]["content"]
            logger.info(f"last_message: {speak_output=}")
            if "CONVERSATION_END" in speak_output:
                # Today's session already wrapped up. "What can I do for you?" was far too
                # open a question for a patient to answer, so say which of the two things
                # is actually on offer: resume the remaining questions, or take an addition.
                patient = _lookup_patient_by_alexa_identity(get_customer_email(handler_input))
                done = (
                    _todays_questions_are_done(patient.id)
                    if patient is not None
                    else False
                )
                speak_output = (
                    "You have finished today's questions. If you have any discomfort, "
                    "please reach out to your providers."
                    if done
                    else "Happy to help you again. Can we continue today's questions?"
                )
                # Record it, so when the patient answers the model sees what was asked
                # instead of a bare reply sitting after CONVERSATION_END.
                if patient is not None:
                    db.session.add(
                        ConversationLog(
                            patient_id=patient.id,
                            role="assistant",
                            chain_of_thoughts="",
                            content=speak_output,
                            date=datetime.utcnow(),
                        )
                    )
                    db.session.commit()
        else:
            speak_output = "Hello, this is the Cardio research study chatbot assistant developed by Northeastern University Human-centered AI lab. We'll go through eight symptom-related questions, which will take about 2 to 5 minutes. Are you ready to start today's questions?"

        logger.info(f"{speak_output=}")
        return to_speech(handler_input, speak_output)


class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Single handler for Cancel and Stop Intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_intent_name("AMAZON.CancelIntent")(
            handler_input
        ) or ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input)

    def handle(self, handler_input):
        logger.info("CancelOrStopIntentHandler")
        logger.info(handler_input.request_envelope)
        user_id = get_customer_email(handler_input)
        if conversationEnded(user_id):
            logger.info("Session ended")
        else:
            logger.error("Failed to end session")
        # type: (HandlerInput) -> Response
        speak_output = "Goodbye!"

        return (
            handler_input.response_builder.speak(speak_output)
            .set_should_end_session(True)
            .response
        )


class SessionEndedRequestHandler(AbstractRequestHandler):
    """Handler for Session End."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        logger.info("SessionEndedRequestHandler")
        logger.info(handler_input.request_envelope)
        user_id = get_customer_email(handler_input)
        if conversationEnded(user_id):
            logger.info("Session ended")
        else:
            logger.error("Failed to end session")

        return handler_input.response_builder.response


class ConversationHandler(AbstractRequestHandler):
    """The intent reflector is used for interaction model testing and debugging.
    It will simply repeat the intent the user said. You can create custom handlers
    for your intents by defining them above, then also adding them to the request
    handler chain below.
    """

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return ask_utils.is_request_type("LaunchRequest")(
            handler_input
        ) or ask_utils.is_request_type("IntentRequest")(
            handler_input
        )  # catch all intent

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        if ask_utils.is_request_type("LaunchRequest")(handler_input):
            message = "hello"
        else:
            if ask_utils.get_slot_value(handler_input, "text"):
                message = ask_utils.get_slot_value(handler_input, "text")
            else:
                message = (
                    ask_utils.get_intent_name(handler_input)
                    .replace("Intent", "")
                    .replace("AMAZON.", "")
                )
        logger.info("ConversationHandler")
        logger.info("message: " + message)
        logger.info(handler_input.request_envelope)
        logger.info(handler_input.request_envelope)
        user_id = get_customer_email(handler_input)
        logger.info(user_id)
        
        try:
            result = conversation(user_id, message)
            speak_output = result["content"]
            logger.info(f"{speak_output=}")
            if "CONVERSATION_END" in speak_output:
                conversationEnded(user_id)
                final_message = speak_output.replace("CONVERSATION_END", "")
                return (
                    handler_input.response_builder.speak(final_message)
                    .set_should_end_session(True)
                    .response
                )

            reprompt_output = REPROMPT_TEXT
            return (
                handler_input.response_builder.speak(speak_output)
                .ask(reprompt_output)
                .set_should_end_session(False)
                .response
            )
        except PatientNotFound:
            speak_output = "We don't have a valid participant ID for you. Please say 'please note my alexa ID' and contact system administrator"
            return (
                handler_input.response_builder.speak(speak_output)
                .set_should_end_session(True)
                .response
            )
        except ConversationError as e:
            logger.error(f"Conversation error: {e}")
            speak_output = "We are encountering a system internal error. Please try again later or contact the system administrator"
            return (
                handler_input.response_builder.speak(speak_output)
                .set_should_end_session(True)
                .response
            )
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            speak_output = "We are encountering a system internal error. Please try again later or contact the system administrator"
            return (
                handler_input.response_builder.speak(speak_output)
                .set_should_end_session(True)
                .response
            )


class CatchAllExceptionHandler(AbstractExceptionHandler):
    """Generic error handling to capture any syntax or routing errors. If you receive an error
    stating the request handler chain is not found, you have not implemented a handler for
    the intent being invoked or included it in the skill builder below.
    """

    def can_handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> bool
        return True

    def handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> Response
        logger.error(exception, exc_info=True)
        if isinstance(exception, EmailPermissionDenied) or (
            isinstance(exception, SerializationException)
            and "ACCESS_DENIED" in str(exception)
        ):
            return (
                handler_input.response_builder.speak(
                    "Please grant permission to access your email address to associate your alexa account with your participant ID"
                )
                .set_card(
                    # ask_sdk_model.ui.ask_for_permissions_consent_card.
                    AskForPermissionsConsentCard(
                        permissions=["alexa::profile:email:read"],
                    )
                )
                .set_should_end_session(True)
                .response
            )
        logger.info(handler_input.request_envelope)

        speak_output = "Sorry, I had trouble doing what you asked. Please try again."

        return (
            handler_input.response_builder.speak(speak_output)
            .ask(speak_output)
            .set_should_end_session(False)
            .response
        )


# The SkillBuilder object acts as the entry point for your skill, routing all request and response
# payloads to the handlers above. Make sure any new handlers or interceptors you've
# defined are included below. The order matters - they're processed top to bottom.


skill_builder = CustomSkillBuilder(api_client=DefaultApiClient())

skill_builder.add_request_handler(LaunchRequestHandler())
skill_builder.add_request_handler(CancelOrStopIntentHandler())
skill_builder.add_request_handler(ConversationHandler())
skill_builder.add_request_handler(SessionEndedRequestHandler())
skill_builder.add_exception_handler(CatchAllExceptionHandler())
