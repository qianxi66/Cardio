# -*- coding: utf-8 -*-

# This sample demonstrates handling intents from an Alexa skill using the Alexa Skills Kit SDK for Python.
# Please visit https://alexa.design/cookbook for additional examples on implementing slots, dialog management,
# session persistence, api calls, and more.
# This sample is built using the handler classes approach in skill builder.
import logging
from datetime import datetime
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
from ask_sdk_core.skill_builder import SkillBuilder
from .app import app, db
from .db import Patient, User, ConversationLog
from .openai_utils import conversation as openai_conversation
from .config import auto_create_patient, mongodb_url, mongodb_client_kwargs
from pymongo import MongoClient

logger = app.logger


def to_speech(handler_input, response):
    break_audio = ' <break time="10s" /> '
    sound_bank_audio = "<prosody volume='silent'> . </prosody>"
    # speak_output = response + break_audio*18 + sound_bank_audio
    speak_output = response
    ask_output = (
        "Anything else I can help? You can repeat your sentence."
        + break_audio * 3
        + sound_bank_audio
    )

    return handler_input.response_builder.speak(speak_output).ask(ask_output).response

def getLastMessage(alexa_user_id: str):
    patient = Patient.query.filter_by(alexa_user_id=alexa_user_id).first()
    if patient is None:
        if auto_create_patient:
            participant_id = alexa_user_id.split("@")[0]
            patient = Patient(
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
    messages = (
        ConversationLog.query.filter_by(patient_id=patient.id)
        .order_by(ConversationLog.date.asc())
        .all()
    )
    if len(messages) == 0:
        # create a new assistant message
        msg = "Hello, this is the Cardio research study chatbot assistant. Are you ready to start today's questions? This skill's content is not intended as a substitute for professional medical advice or treatment."
        message = ConversationLog(
            patient_id=patient.id,
            role="assistant",
            chain_of_thoughts="",
            content=msg,
            date=datetime.utcnow(),
        )
        db.session.add(message)
        db.session.commit()
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
        patient = Patient.query.filter_by(alexa_user_id=alexa_user_id).first()
        logger.info(f"patient: {patient}")
        if patient is None:
            return jsonify({"message": "patient not found"}), 404
        logger.info("session end hook done")
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
        patient = Patient.query.filter_by(alexa_user_id=alexa_user_id).first()
        if patient is None:
            raise PatientNotFound(f"Patient not found for alexa_user_id: {alexa_user_id}")
        
        wearable_data = None
        if patient.participant_id:
            try:
                client = MongoClient(mongodb_url, **mongodb_client_kwargs)
                db2 = client["study_db"]
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
            finally:
                try:
                    client.close()
                except Exception:
                    pass
        
        # Create conversation log for user message
        log = ConversationLog(
            patient_id=patient.id,
            role="user",
            content=content,
            date=datetime.utcnow(),
        )
        db.session.add(log)
        db.session.commit()
        
        # get all conversation logs for this patient
        conversation_logs = (
            ConversationLog.query.filter_by(patient_id=patient.id)
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
            
        assistant_message = openai_conversation(conversation_logs, wearable_data=wearable_data)
        logger.info("Wearable data sent to LLM: %s", wearable_data)
        logger.info(f"assistant_message: {assistant_message}")
        try:
            chain_of_thoughts = assistant_message.split("==============")[0]
            assistant_message = assistant_message.split("==============")[1].strip(" \n")
        except IndexError:
            chain_of_thoughts = """breathing: not discussed
fever: not discussed
stools: not discussed
pain: not discussed
drainage: not discussed
activity: not discussed
conscious: not discussed
constipation: not discussed
diarrhea: not discussed
eating: not discussed
swelling: not discussed
mood: not discussed
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

def get_customer_email(handler_input: HandlerInput) -> str:
    # ups_client = ask_sdk_model.services.ups.ups_service_client.UpsServiceClient()
    # return ups_client.get_customer_email(handler_input)
    try:
        ups_client = handler_input.service_client_factory.get_ups_service()
        result = ups_client.get_profile_email()
        logger.info(result)
        if isinstance(result, str) and result:
            return result
    except Exception as e:
        logger.warning("UPS email lookup failed: %s", e)

    try:
        user_id = handler_input.request_envelope.session.user.user_id
        if user_id:
            return user_id
    except Exception:
        pass

    try:
        user_id = handler_input.request_envelope.context.system.user.user_id
        if user_id:
            return user_id
    except Exception:
        pass

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
                speak_output = "Happy to help you again! What can I do for you?"
        else:
            speak_output = "Hello, this is the Cardio research study chatbot assistant. Are you ready to start today's questions?"

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
                return (
                    handler_input.response_builder.speak(
                        speak_output.replace("CONVERSATION_END", "")
                    )
                    .set_should_end_session(True)
                    .response
                )

            return (
                handler_input.response_builder.speak(speak_output)
                .ask(speak_output)
                .response
            )
        except PatientNotFound:
            return handler_input.response_builder.speak(
                "We don't have a valid participant ID for you. Please say 'please note my alexa ID' and contact system administrator"
            ).response
        except ConversationError as e:
            logger.error(f"Conversation error: {e}")
            return handler_input.response_builder.speak(
                "We are encountering a system internal error. Please try again later or contact the system administrator"
            ).response
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return handler_input.response_builder.speak(
                "We are encountering a system internal error. Please try again later or contact the system administrator"
            ).response


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
                .response
            )
        logger.info(handler_input.request_envelope)

        speak_output = "Sorry, I had trouble doing what you asked. Please try again."

        return (
            handler_input.response_builder.speak(speak_output)
            .ask(speak_output)
            .response
        )


# The SkillBuilder object acts as the entry point for your skill, routing all request and response
# payloads to the handlers above. Make sure any new handlers or interceptors you've
# defined are included below. The order matters - they're processed top to bottom.


skill_builder = SkillBuilder()

skill_builder.add_request_handler(LaunchRequestHandler())
skill_builder.add_request_handler(CancelOrStopIntentHandler())
skill_builder.add_request_handler(ConversationHandler())
skill_builder.add_request_handler(SessionEndedRequestHandler())
skill_builder.add_exception_handler(CatchAllExceptionHandler())
