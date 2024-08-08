# import datetime
import json
import random
from datetime import datetime, timedelta
import bcrypt
import click

from sqlalchemy import text

from .app import app
from .config import symptom_descriptions
from .db import ConversationLog, Patient, Report, ReportNote, ReportSummary, User, db


def initialize_reports():
    with app.app_context():
        patients = Patient.query.all()
        for patient in patients:
            for i in range(10):
                # random state, read false, empty logs
                symptom_kwargs = [
                    {
                        f"{symptom}_state": 0,
                        f"{symptom}_logs": "[]",
                    }
                    for symptom in symptom_descriptions.keys()
                ]
                symptom_kwargs_ = dict(
                    [(k, v) for d in symptom_kwargs for k, v in d.items()]
                )

                likerts = [
                    (
                        f"{symptom}_scale",
                        random.randint(1, 10)
                        if symptom_kwargs_[f"{symptom}_state"] == 2
                        else 0,
                    )
                    for symptom, description in symptom_descriptions.items()
                    if description["likert"]
                ]
                print(symptom_kwargs_)
                print(likerts)
                symptom_kwargs = dict(
                    [(k, v) for d in symptom_kwargs for k, v in d.items()] + likerts
                )
                report = Report(
                    patient_id=patient.id,
                    **symptom_kwargs,
                )
                db.session.add(report)
            # update created_at
            reports = Report.query.filter_by(patient_id=patient.id).all()
            for i, report in enumerate(reports):
                report.created_at = datetime.utcnow() - timedelta(days=(i + 1))
                db.session.add(report)
            patient.state = max(
                [
                    symptom_descriptions[symptom]["max_scale"]
                    if getattr(reports[0], f"{symptom}_state") == 2
                    else getattr(reports[0], f"{symptom}_state")
                    for symptom in symptom_descriptions.keys()
                ]
            )
            db.session.add(patient)
        db.session.commit()


def generate_conversation_logs():
    with app.app_context():
        reports = Report.query.all()
        for report in reports:
            for _ in range(10):  # Generate 10 logs per report
                log = ConversationLog(
                    patient_id=report.patient_id,
                    report_id=report.id,
                    role=random.choice(["assistant", "user"]),
                    content=random.choice(
                        [
                            "How are you feeling today?",
                            "I'm feeling okay, just a bit tired.",
                            "Make sure to rest. Do you need any help with your medication?",
                            "Yes, please remind me to take my medication at 7 PM.",
                            "Will do. Do you have any other concerns?",
                            "No, that's all for today. Thank you.",
                            "You're welcome! Have a good day.",
                        ]
                    ),
                    created_at=datetime.utcnow(),
                )
                db.session.add(log)
            db.session.commit()


def update_reports():
    with app.app_context():
        reports = Report.query.all()
        for report in reports:
            logs = ConversationLog.query.filter_by(report_id=report.id).all()
            log_ids = [log.id for log in logs]
            for symptom in symptom_descriptions.keys():
                # find random logs
                random_logs = random.sample(log_ids, 3)
                setattr(report, symptom + "_logs", json.dumps(random_logs))
            db.session.add(report)
        db.session.commit()


def generate_summaries():
    with app.app_context():
        report = Report.query.all()
        for r in report:
            for i in range(5):
                summary = ReportSummary(
                    report_id=r.id,
                    category=random.choice(
                        ["Summary", "Additional Comments", "Recommendations"]
                    ),
                    content=random.choice(
                        [
                            "Patient is feeling better today",
                            "Patient is feeling worse today",
                            "Patient is feeling the same today",
                        ]
                    ),
                    conversation_log_ids="",
                    highlight_keywords="",
                )
                db.session.add(summary)
        db.session.commit()


def generate_notes():
    with app.app_context():
        report = Report.query.all()
        for r in report:
            for i in range(3):
                note = ReportNote(
                    report_id=r.id,
                    user_id=0,
                    content=random.choice(
                        [
                            "should check in with patient tomorrow",
                            "shouldn't be a problem",
                            "keep watch",
                        ]
                    ),
                )
                db.session.add(note)
        db.session.commit()


@app.cli.command("generate-reports")
def generate_reports():
    initialize_reports()
    # generate_conversation_logs()
    # update_reports()


@app.cli.command("generate-summaries")
def generate_summaries_cmd():
    generate_summaries()


@app.cli.command("generate-notes")
def generate_notes_cmd():
    generate_notes()


@app.cli.command("generate-patients")
def generate_patients():
    with app.app_context():
        with db.engine.connect() as connection:
            sql = """INSERT INTO patient VALUES(1, 25, 'male', 'E01-01', NULL, 'no information', 'no information', 'T001 Alex', '1970-01-01', false, 0);
INSERT INTO patient VALUES(2, 26, 'female', 'E01-02', NULL, 'no information', 'no information', 'T002 Bella', '1970-01-01', false, 0);
INSERT INTO patient VALUES(3, 27, 'male', 'E01-03', NULL, 'no information', 'no information', 'T003 Charlie', '1970-01-01', false, 0);
INSERT INTO patient VALUES(4, 28, 'female', 'E01-04', NULL, 'no information', 'no information', 'T004 Dana', '1970-01-01', false, 0);
INSERT INTO patient VALUES(5, 29, 'male', 'E01-05', NULL, 'no information', 'no information', 'T005 Ethan', '1970-01-01', false, 0);
INSERT INTO patient VALUES(6, 30, 'female', 'E01-06', NULL, 'no information', 'no information', 'T006 Fiona', '1970-01-01', false, 0);
INSERT INTO patient VALUES(7, 31, 'male', 'E01-07', NULL, 'no information', 'no information', 'T007 George', '1970-01-01', false, 0);
INSERT INTO patient VALUES(8, 32, 'female', 'E01-08', NULL, 'no information', 'no information', 'T008 Hannah', '1970-01-01', false, 0);
INSERT INTO patient VALUES(9, 33, 'male', 'E01-09', NULL, 'no information', 'no information', 'T009 Ian', '1970-01-01', false, 0);
INSERT INTO patient VALUES(10, 34, 'female', 'E01-10', NULL, 'no information', 'no information', 'T010 Jenna', '1970-01-01', false, 0);
INSERT INTO patient VALUES(11, 35, 'male', 'E01-11', NULL, 'no information', 'no information', 'T011 Kyle', '1970-01-01', false, 0);
INSERT INTO patient VALUES(12, 36, 'female', 'E01-12', NULL, 'no information', 'no information', 'T012 Lily', '1970-01-01', false, 0);
INSERT INTO patient VALUES(13, 37, 'male', 'E01-13', NULL, 'no information', 'no information', 'T013 Max', '1970-01-01', false, 0);
INSERT INTO patient VALUES(14, 38, 'female', 'E01-14', NULL, 'no information', 'no information', 'T014 Nora', '1970-01-01', false, 0);
INSERT INTO patient VALUES(15, 39, 'male', 'E01-15', NULL, 'no information', 'no information', 'T015 Oliver', '1970-01-01', false, 0);
"""
            for statement in sql.split(";"):
                connection.execute(text(statement))
            connection.execute(text("COMMIT;"))
        db.session.commit()
        ids = {
            "Yuxuan": "amzn1.ask.account.AMAUHCXHP5MDPU5NLIJ5RHL4B34PTBWUQSSGBUAK2RASAITVGFUI3BAZLBNAXCE6PYH7GLGDJF5NASF7XGM3QRZK3YGXOB5RBDUP5W2ZWGSBFQ5HSCFO7PSVKF5SKM4RGDYIBCOHPCOBDWHF6XUJ2OFBVCXSJECSDC7NTUQWKK3SCM52XCIIXOPSGHN4XV6GLWD3XQCOOQJFOKO6PRYYRHAV3DZJD7NBTRENFR5R3M",
            "Dakuo": "amzn1.ask.account.AMAWXW5L73FFN6BCC27OKNAGHXKBC6THXK6FLAB4DM6NV3YTMHQMH3TKQJO7XGAG2THUFA4P4DELNR46L2AJBBOI7GWDCK3HKTIIVEDTHVQHUDYLSVSTWZJD2RWHNAZH7ZPN5GBYTTMPUOSPDCEORHFWJQP3JTGKDRFMVMBLHPLITWIHOEA6MS7K6RLXAKNXM46GQIAPQPOI6XC6QJVX34CMLKJUUIDTYT7XHSGJOCIA",
            "Jiachen": "amzn1.ask.account.AMA7ZSZ6R5XT6YD23IAFJGTQGW2D6EYQHN22XU5ITEV6ICBAQGRL22U6GHSDILAUOH5VAPZ5CA33BFAVV4ARH3TVJPP53BPINGGJVLMB63TKFQL7DRNJGQOA6X3325Q5RWDRB2SFTUWRJMRQD3LWIMKVDFH4H77V5UQDVPQISFICTJS6RT2SDWDSO2PSLLPDRPIHO5BHRQKLXD5NWZY46KAY7Y4OUEN4RF3CI4LYKSRQ",
            "Ziqi": "amzn1.ask.account.AMATTDONXW34ZAJ6S3VHVVETE3BQ4ZIDZMO4WSV3VW63ADZUZX4Q3LLO4A4M3N2OOTUDS4EOY4E54N6HEBN4FWZAIQURU6UNI4XW2OWEH7VDIYGGY5DKJZINWCFW7SHKE4QNCTXM7XNMXZY5NKA5W75OVRM2K4FQXPTB45SEBFP5OFZJCQAIQPJIQQDUFTPSIPRW7MAK3GZKLIWA25LGCR6H5G5XN7G4OMIHIZYIAHPA",
        }
        for key in ids:
            patient = Patient(
                age=25,
                gender="male",
                EHR_id=f"TEST-{key}",
                alexa_user_id=ids[key],
                medical_history="no information",
                medication="no information",
                reviewed=False,
                state=0,
                last_read_at=datetime(1970, 1, 1),
                participant_id=f"TEST-{key}",
            )
            db.session.add(patient)
        db.session.commit()
        print("Patients generated.")


# @app.cli.command("generate-users")
# def generate_users():
#     with app.app_context():
#         with db.engine.connect() as connection:
#             sql = """INSERT INTO user VALUES(1,'sunbo','123','test@gmail.com','sunbo');
#             INSERT INTO user VALUES(2,'abab','456','test2@gmail.com','abab');"""
#             for statement in sql.split(";"):
#                 connection.execute(text(statement))
#             connection.execute(text("COMMIT;"))
#         db.session.commit()
#         print("users generated.")


@app.cli.command("create-user")
@click.option("--username", required=True, type=str, help="Username for the new user")
@click.option("--password", required=True, type=str, help="Password for the new user")
@click.option("--email", required=True, type=str, help="Email for the new user")
@click.option("--name", required=True, type=str, help="Real name for the new user")
def create_user(username, password, email, name):
    with app.app_context():
        print(f"Creating user with username {username}")

        # Check if the username or email already exists
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        if existing_user:
            print(f"User with username '{username}' or email '{email}' already exists.")
            return

        hashed_password = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        user = User(username=username, password=hashed_password, email=email, name=name)
        db.session.add(user)
        db.session.commit()

        print(f"User '{username}' created successfully.")


@app.cli.command("remove-conversation-summaries")
def remove_conversation_summaries():
    with app.app_context():
        patient_ids = [6, 7, 8, 10, 11, 12, 13, 14, 15]
        for pid in patient_ids:
            reports = Report.query.filter_by(patient_id=pid).all()
            for report in reports:
                summaries = ReportSummary.query.filter_by(report_id=report.id).all()
                for summary in summaries:
                    db.session.delete(summary)
                conversations = ConversationLog.query.filter_by(
                    report_id=report.id
                ).all()
                for conversation in conversations:
                    db.session.delete(conversation)
                notes = ReportNote.query.filter_by(report_id=report.id).all()
                for note in notes:
                    db.session.delete(note)
        db.session.commit()
    report_ids = [151, 152, 158, 153, 154, 155, 156, 157]
    with app.app_context():
        reports = Report.query.filter(Report.id.not_in(report_ids)).all()
        for report in reports:
            summaries = ReportSummary.query.filter_by(report_id=report.id).all()
            for summary in summaries:
                db.session.delete(summary)
            conversations = ConversationLog.query.filter_by(report_id=report.id).all()
            for conversation in conversations:
                db.session.delete(conversation)
            notes = ReportNote.query.filter_by(report_id=report.id).all()
            for note in notes:
                db.session.delete(note)
        db.session.commit()


# INSERT INTO patient VALUES(16, 71, 'male', 'TTTT', NULL, 'no information', 'no information', 'TEST dakuo', '1970-01-01', false, 0);
# INSERT INTO patient VALUES(17, 71, 'male', 'TTTT', NULL, 'no information', 'no information', 'TEST yuxuan', '1970-01-01', false, 0);
# INSERT INTO patient VALUES(16, 71, 'male', 'TTTT', NULL, 'no information', 'no information', 'TEST dakuo', '1970-01-01', false, 0);
# INSERT INTO patient VALUES(18, 18, 'female', 'TEST-Jiachen', 'amzn1.ask.account.AMA7ZSZ6R5XT6YD23IAFJGTQGW2D6EYQHN22XU5ITEV6ICBAQGRL22U6GHSDILAUOH5VAPZ5CA33BFAVV4ARH3TVJPP53BPINGGJVLMB63TKFQL7DRNJGQOA6X3325Q5RWDRB2SFTUWRJMRQD3LWIMKVDFH4H77V5UQDVPQISFICTJS6RT2SDWDSO2PSLLPDRPIHO5BHRQKLXD5NWZY46KAY7Y4OUEN4RF3CI4LYKSRQ', 'no information', 'no information', 'TEST jiachen', '1970-01-01', false, 0);
# INSERT INTO patient VALUES(19, 19, 'female', 'TEST-Ziqi', 'amzn1.ask.account.AMATTDONXW34ZAJ6S3VHVVETE3BO4ZIDZMO4WSV3VW63ADZUZX403LLO4A4M3N200TUDS4E0Y4E54N6HEBN4FWZAIOURU6UNI4XW20WEH7VDIYGGY5DKJZINWCFW7SHKE4ONCTXM7XNMXZY5NKA5W750VRM2K4FOXPTB45SEBFP50FZJCQAIQPJIQQDUFTPSIPRW7MAK3GZKLIWA25LGCR6H5G5XN7G40MIHIZYIAHPA', 'no information', 'no information', 'TEST ziqi', '1970-01-01', false, 0);
