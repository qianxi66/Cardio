# import datetime
import json
import random
from datetime import datetime, timedelta

from sqlalchemy import text

from .app import app
from .config import symptom_descriptions
from .db import ConversationLog, Patient, Report, ReportNote, ReportSummary, db


def initialize_reports():
    with app.app_context():
        patients = Patient.query.all()
        for patient in patients:
            for i in range(10):
                # random state, read false, empty logs
                symptom_kwargs = [
                    {
                        f"{symptom}_state": 0,
                        f"{symptom}_logs": "",
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
            sql = """
INSERT INTO patient VALUES(1, 0, 'male', 'N00-00', NULL, 'no information', 'no information', 'PATIENTID_UNDEFINED', '1970-01-01', false, 0);
INSERT INTO patient VALUES(2, 0, 'male', 'N00-00', NULL, 'no information', 'no information', 'PATIENTID_UNDEFINED', '1970-01-01', false, 0);
INSERT INTO patient VALUES(3, 0, 'male', 'N00-00', NULL, 'no information', 'no information', 'PATIENTID_UNDEFINED', '1970-01-01', false, 0);
INSERT INTO patient VALUES(4, 0, 'male', 'N00-00', NULL, 'no information', 'no information', 'PATIENTID_UNDEFINED', '1970-01-01', false, 0);
INSERT INTO patient VALUES(5, 0, 'male', 'N00-00', NULL, 'no information', 'no information', 'PATIENTID_UNDEFINED', '1970-01-01', false, 0);
INSERT INTO patient VALUES(6, 0, 'male', 'N00-00', NULL, 'no information', 'no information', 'PATIENTID_UNDEFINED', '1970-01-01', false, 0);
INSERT INTO patient VALUES(7, 0, 'male', 'N00-00', NULL, 'no information', 'no information', 'PATIENTID_UNDEFINED', '1970-01-01', false, 0);
INSERT INTO patient VALUES(8, 0, 'male', 'N00-00', NULL, 'no information', 'no information', 'PATIENTID_UNDEFINED', '1970-01-01', false, 0);
INSERT INTO patient VALUES(9, 0, 'male', 'N00-00', NULL, 'no information', 'no information', 'PATIENTID_UNDEFINED', '1970-01-01', false, 0);
INSERT INTO patient VALUES(10, 0, 'male', 'N00-00', NULL, 'no information', 'no information', 'PATIENTID_UNDEFINED', '1970-01-01', false, 0);
"""
            for statement in sql.split(";"):
                connection.execute(text(statement))
            connection.execute(text("COMMIT;"))
        db.session.commit()
        ids = {
            # "Yuxuan": "amzn1.ask.account.AMAUHCXHP5MDPU5NLIJ5RHL4B34PTBWUQSSGBUAK2RASAITVGFUI3BAZLBNAXCE6PYH7GLGDJF5NASF7XGM3QRZK3YGXOB5RBDUP5W2ZWGSBFQ5HSCFO7PSVKF5SKM4RGDYIBCOHPCOBDWHF6XUJ2OFBVCXSJECSDC7NTUQWKK3SCM52XCIIXOPSGHN4XV6GLWD3XQCOOQJFOKO6PRYYRHAV3DZJD7NBTRENFR5R3M",
            # "Dakuo": "amzn1.ask.account.AMAWXW5L73FFN6BCC27OKNAGHXKBC6THXK6FLAB4DM6NV3YTMHQMH3TKQJO7XGAG2THUFA4P4DELNR46L2AJBBOI7GWDCK3HKTIIVEDTHVQHUDYLSVSTWZJD2RWHNAZH7ZPN5GBYTTMPUOSPDCEORHFWJQP3JTGKDRFMVMBLHPLITWIHOEA6MS7K6RLXAKNXM46GQIAPQPOI6XC6QJVX34CMLKJUUIDTYT7XHSGJOCIA",
            # "Jiachen": "amzn1.ask.account.AMA7ZSZ6R5XT6YD23IAFJGTQGW2D6EYQHN22XU5ITEV6ICBAQGRL22U6GHSDILAUOH5VAPZ5CA33BFAVV4ARH3TVJPP53BPINGGJVLMB63TKFQL7DRNJGQOA6X3325Q5RWDRB2SFTUWRJMRQD3LWIMKVDFH4H77V5UQDVPQISFICTJS6RT2SDWDSO2PSLLPDRPIHO5BHRQKLXD5NWZY46KAY7Y4OUEN4RF3CI4LYKSRQ",
            # "Ziqi": "amzn1.ask.account.AMATTDONXW34ZAJ6S3VHVVETE3BQ4ZIDZMO4WSV3VW63ADZUZX4Q3LLO4A4M3N2OOTUDS4EOY4E54N6HEBN4FWZAIQURU6UNI4XW2OWEH7VDIYGGY5DKJZINWCFW7SHKE4QNCTXM7XNMXZY5NKA5W75OVRM2K4FQXPTB45SEBFP5OFZJCQAIQPJIQQDUFTPSIPRW7MAK3GZKLIWA25LGCR6H5G5XN7G4OMIHIZYIAHPA",
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


@app.cli.command("set-patient-id")
def set_patient_id():
    account_ids = [
        "amzn1.ask.account.AMAYRBA5RJEIJNALKNF4JC5HVSRA2NKLF6RUBGQAHR2VKXSSZPUQXLQ6N4ZIXWX2AZBMNEBXBZQMJTPBYY7NCQR6NCBYFYPZ3KY7QLU7ET6GYISGXOIEBH54CGS74SCKUJVET2VP7LX73GCGP42NA6ELFDCSSLAYQCM6ADHHC6VGXODIWDNQNI7HIIY6ICBWZQ6TV7PTX7ZSQVKGJVAWTXDBFGGRK27PTI6BFDO4QA",
        "amzn1.ask.account.AMAQQME4URE43VNXWUEJ5CK36E57UGW63X4D32BH3WZMQMTW6G3OZAOC62WUNLMWPSBJTZJU4IQWVXQZOW2A4VXFTABYBXV3WUPFEY3C57LLKHTDB4VNMA2QWIPWUY3TGQFKOIFJ5ZFQT7LAXKOKNZK4EEHOITSDSDPFEOCEXJAIAS4FANOUZGROFNDL4OL37EGKWHCFKHF7IHOACUXLFOXBACXV25IENDTL4T4ALFAQ",
        "amzn1.ask.account.AMA2DDUN6C3YB5WX6SZLZBUIPFDHC4KDBY3XSRMU6SCGVT5M5ZNG23U7FORP3BV6Z3E3B5QLU6YYRMQHQEHBLQCWDY2ORCTLRX4XTK6QCUZCOBXEMWW7BAN77ZNKFUEG6FZRGEFCFDQG3XUS6INYVKE5LPUL2N4ISIUWSCETK3MBCFXBENRMQB5BY7YIFED7MZ3LOX3GO6SCDYWGJ4AADDG4BJPI6ONTNBDXQ5VO4U2A",
        "amzn1.ask.account.AMAVVR372OBNIG6TAGPOSHHBGQC2K7RLGXOEHD2L4DZPI655Q5C7RHVFC2WTVSVDBNNVW4WBCE63G43VJKOZRGRVRV436ZC247AZU6BU56SKMXYHFL7AXD4SIFCNGN3I4G54YLQII427OITNSBZFCOMDMLRPMALHY43RZYJBO4NTWFYOKTTIWFUUROUZYYVTPLCI7WLD5AVIH6WXNATIEFIJJ6IQR4PQZQ7NRFMIK5XQ",
        "amzn1.ask.account.AMAZAREWLW5WD22BE4ZUWBRSDYKNGUGZOVOXR7CEZBL67H7QY5QAGP7NYK3K7DVEVGQYHGZPWPTN2BFUIDVNKWIWIW7E3QLFVNNWFHXXZ6LO6HMUNJTEKF7CO75CXSIJVVFMXUMNLFEZZ7YY6RUNOHWE2AJSFH6WTIX2DZUUVML5VYOXZ263XTDGWTAIXQMEMKJGPKDSYRVCVTURRAXV4XP2ZMDO6LEA7C7WTKRYHU",
        "amzn1.ask.account.AMAR6NF6TEPSXBAKJOQTQFQZEK3KYZKPOSIY5HQOR2D55GVQRQHXUTOT635J4BJRKEPAEJL5FCOPYQ6PZRIHBREKISBHE6J6VP7QFO36CWLWB2CS3J5C6YUIAWUSBRVKR3J5HJN2POUQYYO3IEJOR7ACD52BLIQ5PODD4MHIKCHVRFZUW7UMFRFBHRSD66DAYRYQR4DRZLMRRSURI35N3ZIGD2UTRMP4PUVWSYPAPLIA",
        "amzn1.ask.account.AMAUP2GXJYGJOR6BTIBFUSFZX6SAE3BGZWV4F7UXECNPMFGQEIH7CR7USL6S4YWOZRXTUUFYPXEDF3SG3IOIZIBWEHSKGZ7DEDSKKAT3IHTXOU567FLUUJFQIHT2WFQYZ2KXCIOOYFBCHP6MU6IQTD3G7RW2JCFSXEPTBG4VDRNMYEKS3QA6URZO3RFFJA32FLKBPNVIF6UORTVAB36XCRHU7YB2RH6Z2BGMX7Y4IY",
        "amzn1.ask.account.AMA3MWDGGDILZPVSTPPDZOVSSJZVOJNIA3M35QDOOWH5BTQOJCDXKWIMB3HQBPMVZZUUHI6VLZD3VFZQKKE3ZCIDDCNYUSG4XTQJXOWL2PFK7HHKCZINI6KQU7V2P2CWTA66TDRMPSSNU6RRAJREBEQNKOAQR6RJADEP5YNQIXUHHF2A63NKJAKPOMFZVHONZJUC4MX4Q3BRDF5UAXQNUSZUJ6KK3ZVGXRXLWCEENCQA",
        "amzn1.ask.account.AMA4W5NPQQBTVQVP2OZIOKKZVZMSJ4Q55T4I6ILBVWAGAM3MULBFZSLFHRULBDTAC7KVVXGU6KVX2WAMEEVNOWKTCNFFRZ7HBJ3T3RH2MPOWCHJ5MBZASKXV3K3LUBANUZ5V23CE7557KAVUTTOJKCQ6MMIX3OUONNNG4NRD4DKI55EJD3HIDQQY32SHRM4Z6ZJAJN7WVT4UHFMM2C4JKIWMVNR53BJJAQ5AN3DXYRBQ",
        "amzn1.ask.account.AMATWPD6ITYBAHD7BLNVHRI66NJWVIOSUBBITTI2MWA7HZRULW3IGJZQCDQVK6IQK7O7AMTMP4YUJVUTG6T77AZDKWCT4POSEFLU7MFDM4G6IHSIWI6PFWFOR2AOCEYQSZZ2SBFVTFTTI3JY5KTUZZOTYBOCJ62CUY4NOSAJ3UZFKEVWPRMUVY5XHVJ3I7U2FUNG3QHML5Q7D5KYDSHUURE2S4RMPSLA5COHPSNTNM",
    ]
    for index, alexa_id in enumerate(account_ids):
        p = Patient.query.filter_by(id=index + 1).first()
        p.alexa_user_id = alexa_id
        db.session.add(p)
    db.session.commit()


# INSERT INTO patient VALUES(16, 71, 'male', 'TTTT', NULL, 'no information', 'no information', 'TEST dakuo', '1970-01-01', false, 0);
# INSERT INTO patient VALUES(17, 71, 'male', 'TTTT', NULL, 'no information', 'no information', 'TEST yuxuan', '1970-01-01', false, 0);
# INSERT INTO patient VALUES(16, 71, 'male', 'TTTT', NULL, 'no information', 'no information', 'TEST dakuo', '1970-01-01', false, 0);
# INSERT INTO patient VALUES(18, 18, 'female', 'TEST-Jiachen', 'amzn1.ask.account.AMA7ZSZ6R5XT6YD23IAFJGTQGW2D6EYQHN22XU5ITEV6ICBAQGRL22U6GHSDILAUOH5VAPZ5CA33BFAVV4ARH3TVJPP53BPINGGJVLMB63TKFQL7DRNJGQOA6X3325Q5RWDRB2SFTUWRJMRQD3LWIMKVDFH4H77V5UQDVPQISFICTJS6RT2SDWDSO2PSLLPDRPIHO5BHRQKLXD5NWZY46KAY7Y4OUEN4RF3CI4LYKSRQ', 'no information', 'no information', 'TEST jiachen', '1970-01-01', false, 0);
# INSERT INTO patient VALUES(19, 19, 'female', 'TEST-Ziqi', 'amzn1.ask.account.AMATTDONXW34ZAJ6S3VHVVETE3BO4ZIDZMO4WSV3VW63ADZUZX403LLO4A4M3N200TUDS4E0Y4E54N6HEBN4FWZAIOURU6UNI4XW20WEH7VDIYGGY5DKJZINWCFW7SHKE4ONCTXM7XNMXZY5NKA5W750VRM2K4FOXPTB45SEBFP50FZJCQAIQPJIQQDUFTPSIPRW7MAK3GZKLIWA25LGCR6H5G5XN7G40MIHIZYIAHPA', 'no information', 'no information', 'TEST ziqi', '1970-01-01', false, 0);
