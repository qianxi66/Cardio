
# RECOVER System

## TO discuss

1. user / authentication structure
   1. we have two types of users right? patient and caregiver?
   2. the latter should have things like username / password?
   3. does all caregiver have access to all patients? if not, is it a "many-to-many" relationship or a "many-to-one" relationship?
   4. We don't need to implement things like creating new patients or editing it's information right? For the demo video we can just manually update the database
2. 

## ER

### Patient

A patient

| column           | type    | description                                                  |
| ---------------- | ------- | ------------------------------------------------------------ |
| id               | uint    |                                                              |
| age              | uint    |                                                              |
| gender           | string  | M or F?                                                      |
| ?                | ?       | What is the "E78-02" in the system figma                     |
| alexa_user_id    | ?       |                                                              |
| medical history? | ?       | the "medical history" in the system figma<br />is this going to change? or it's just a fixed thing |
| medication       | string? | the "medication" pannel in the system figma<br />markdown text? |

### User

A caregiver

| column   | type   | description     |
| -------- | ------ | --------------- |
| id       | uint   |                 |
| username | string |                 |
| password | string | Hashed password |
| email    | string |                 |
| name     | string | real name       |

### Report

Report for a single day. May contain multple conversations.

| column      | type          | description                                          |
| ----------- | ------------- | ---------------------------------------------------- |
| id          | uint          |                                                      |
| patient_id  | uint          |                                                      |
| created_at  | datetime      |                                                      |
| updated_at  | datetime      |                                                      |
| pain        | uint          | 0: no information; 1 green; 2 blue; 3 yellow; 4 red? |
| bleeding    |               |                                                      |
| obstruction |               |                                                      |
| chest_pain  |               |                                                      |
| blood_clots |               |                                                      |
| infections  |               |                                                      |
| medications |               |                                                      |
| mobility    |               |                                                      |
| neuropsych  | same as above | same as above                                        |

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
| notes               | string       | notes that can be edited by the user                         |

### ConversationLog

a single message in the conversation.

| column     | type     | description       |
| ---------- | -------- | ----------------- |
| id         | uint     |                   |
| patient_id | uint     |                   |
| report_id  | uint     |                   |
| type       | string   | assistant or user |
| content    | string   |                   |
| created_at | datetime |                   |
|            |          |                   |

