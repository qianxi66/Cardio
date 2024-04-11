
# RECOVER System

## TO discuss

1. user / authentication structure
   1. we have two types of users right? patient and caregiver? `two types of users, patients (using alexa) and professionals (monitoring dashboard). (btw, "caregiver" usually refers to the family members of the patient)`
   2. the latter should have things like username / password? `yes. Currently we can just have username / password; it may be good to have some test users in the dev stage`
   3. does all caregiver have access to all patients? if not, is it a "many-to-many" relationship or a "many-to-one" relationship? `Currently we can set: all professionals have access to all patients, since there will not be many users monitoring the dashboard and all patients are anonymized. `
   4. We don't need to implement things like creating new patients or editing it's information right? For the demo video we can just manually update the database `I agree`
2.


## ER

### Patient

A patient

| column           | type    | description                                                  |
| ---------------- | ------- | ------------------------------------------------------------ |
| id               | uint    |                                                              |
| age              | uint    |                                                              |
| gender           | string  | `male vs female`                                                |
| EHR_id          | String | a patient number or identifier in EHR                   |
| alexa_user_id    | String |                                                               |
| medical_history | String | the "medical history" in the system figma<br />leave empty for now |
| medication       | string | the "medication" pannel in the system figma |
| participant_id | string | 1-15 but stored as strings so in case we need P1 in the future |

### User

A professional and dashboard user

| column   | type   | description     |
| -------- | ------ | --------------- |
| id       | uint   |                 |
| username | string |                 |
| password | string | Hashed password |
| email    | string |                 |
| name     | string | real name       |

### Report

Report for a single day. May contain multple conversations.

| column      | type          | description                                         |
| ----------- | ------------- | --------------------------------------------------- |
| id          | uint          |                                                     |
| patient_id  | uint          |                                                     |
| created_at  | datetime      |                                                     |
| updated_at  | datetime      |                                                     |
| pain        | uint          | 0: no information; 1 green; 2 blue; 3 yellow; 4 red |
| bleeding    |               |                                                     |
| obstruction |               |                                                     |
| chest_pain  |               |                                                     |
| blood_clots |               |                                                     |
| infections  |               |                                                     |
| medications |               |                                                     |
| mobility    |               |                                                     |
| neuropsych  | same as above | same as above                                       |

### ReportNote

A single note entry for a day

don't allow edit; allow delete

| column     | type     | description        |
| ---------- | -------- | ------------------ |
| id         | uint     |                    |
| report_id  | uint     |                    |
| user_id    | Uint     |                    |
| content    | string   |                    |
| created_at | datetime |                    |
| updated_at | Datetime | don't allow update |



### ReportSummary

the "conversation summary" part of the system.

Each report have a series of summaries. Will be displayed in the system as bullet points.

| column              | type         | description                                                  |
| ------------------- | ------------ | ------------------------------------------------------------ |
| id                  | uint         |                                                              |
| report_id           | Uint         |                                                              |
| category            | string       | like "symptoms" and "additional comments"; will used to group summaries in the frontend |
| content             | string       |                                                              |
| conversaion_log_ids | list of uint | used by the click to jump to specific log function           |
| highlight_keywords  | string       | a list of keywords seperated by ","                          |

### ConversationLog

a single message in the conversation.

| column     | type     | description       |
| ---------- | -------- | ----------------- |
| id         | uint     |                   |
| patient_id | uint     | `correspond to?`                  |
| report_id  | uint     |  `what is report_id?`                 |
| type       | string   | assistant or user |
| content    | string   |                   |
| created_at | datetime |                   |

```
Additional comments:
1. About user ids in this system: can check "Account Info-15 Patients" google doc for examples
   a. user_id in alexa looks like this: "amzn1.ask.account.AMA4HPFUU4CDU5GP3IVM7EQBJFJ7QU3D4HLOEQFEMOCERCUNRIOCT4APS54YYWL3HI3AYG4G6WSKJ7DCTIHXUZIV5J7ME4DXSO4OKSYROLFBSKNCNPQ2QIU2TLHQNRS2KYC7PPDICRKQXY2UXWXUR4IVWHZOLAA4C7XNH5FL7JVLQO26LQUO7F5BAXWUSG6PUKO64MSDRU66STXWK7QBWQDHNTZIRBPBLZBCGWPQAM". It is generated by Alexa skill service. We use this to differentiate between alexa accounts.
   b. On the dashboard and to the technical team, each participant has a participant number (1 to 15). There is also a table mapping participant numbers to their alexa account user_ids.
   c. The professionals viewing the dashboard will have a list of participants mapping participant numbers (1 to 15) with real names, which is confidential.
```
