# How Alexa Skill Links to a Patient (e.g. test002)

## What the backend uses as "Alexa user ID"

When a user talks to the skill, the backend needs one identifier to look up the patient. That value comes from **`get_customer_email(handler_input)`** in `recover/alexa.py`. It is used everywhere as `alexa_user_id`:

1. **First**: Try **Alexa User Profile Service (UPS)** to get the user's **email** (requires the skill to request email permission and the user to grant it).  
   - In your setup this usually fails with: `UPS email lookup failed: ... no configured API client`, so the backend does not use email.

2. **Fallback**: Use the **Amazon account ID** from the request:
   - `handler_input.request_envelope.session.user.user_id`, or
   - `handler_input.request_envelope.context.system.user.user_id`  
   Example: `amzn1.ask.account.AMA6YCWRCW32OFWVQ7JEQBLQMFEPBAGDEM4RNO6K4PZOLNG7RTZSBF2VZANCTBVJBFAL57J3ZUBWFWNRIPNPEF6ZT7ELP54JEJE3TFIZH3I3DHKM7FT5JB5YZNWANNG4FWDA7H6EWO7ZTIUJVBUKA2FTXRS2E2BY2YCMDZFALE36CPCOKTUZJ54R6HDWWZRQMGIPVOUSPLWV4ABYLOPGKJX3H6VQV55SDZM4R374G46A`

So in practice the "alexa user id" the backend uses is this **long Amazon account ID**, not email and not a short code like `alexa-002`.

## How the link to a patient works

- Every handler that needs the patient does:  
  `patient = Patient.query.filter_by(alexa_user_id=alexa_user_id).first()`  
  where `alexa_user_id` is the string returned by `get_customer_email(handler_input)`.
- So **whoever is using the Echo must have their `Patient.alexa_user_id` in the database equal to that exact string** (the Amazon ID above).  
- For that Echo/user to be "connected to patient test002", the **patient row that has `participant_id = test002`** must have **`alexa_user_id` = that same Amazon ID**.

There is no separate "link" step in code: the only link is that one field on `Patient`.

## How it was (or can be) connected to test002

1. **Manual link (most likely)**  
   - Get the Amazon user ID that the Echo sends (e.g. from backend logs when that user opens the skill, or from Alexa developer console / testing).  
   - In the **dashboard (internal web)** open the patient that should be test002 (e.g. "Michael Brown" / test002).  
   - In the patient form, the field labeled **"Email"** is actually **`alexa_user_id`**. Set it to that **full Amazon account ID** (not an email, not `alexa-002`).  
   - Save. From then on, when that Echo/user invokes the skill, the backend receives the same ID and finds that patient (test002).

2. **Seeded / CLI data**  
   - Seed or CLI may create patients with `alexa_user_id` like `alexa-001`, `alexa-002`, etc. Those **do not** match the real ID Alexa sends. So for a real device to be "connected to test002", someone must have **updated** the test002 patient’s `alexa_user_id` to the real Amazon ID (e.g. via the dashboard as in (1)).

3. **Auto-create**  
   - If no patient is found and `auto_create_patient` is true, the backend creates a **new** patient with `alexa_user_id = <Amazon ID>` and `participant_id = "AUTO_" + <Amazon ID>`. That does **not** attach to an existing test002; it creates a new participant. So "already connected to test002" means the existing test002 row was linked by setting its `alexa_user_id` (as in (1)).

## Can I use email to link?

**Short answer: Currently NO, but theoretically YES if UPS is configured.**

### Current situation (email won't work)
- The backend tries to get email via **UPS (User Profile Service)** first, but it fails with: `UPS email lookup failed: ... no configured API client`
- So even if you set `alexa_user_id` to an email in the database, the backend will **fallback to Amazon account ID** and won't match the email
- **Result:** Email-based linking doesn't work right now

### To enable email-based linking

1. **Configure UPS in Alexa Developer Console:**
   - In your skill's configuration, enable **User Profile Service (UPS)** and request **email permission**
   - The skill code already requests this permission (see line 431 in `alexa.py`: `permissions=["alexa::profile:email:read"]`)

2. **User must grant permission:**
   - When the user first uses the skill, Alexa will ask them to grant email access
   - They must say "yes" or grant it in the Alexa app

3. **Then you can use email:**
   - Once UPS works, `get_customer_email()` will return the user's email address
   - You can then set `Patient.alexa_user_id` to that email in the database
   - The backend will match by email instead of Amazon account ID

### Current workaround (use Amazon account ID)
Since email doesn't work now, you must use the **Amazon account ID**:
1. Have the user open the skill once (or test in Alexa Developer Console)
2. Check backend logs to find the `user_id` (Amazon account ID) that was used
3. Set `Patient.alexa_user_id` to that exact Amazon account ID in the dashboard

## Summary

- **Link = one field:** `Patient.alexa_user_id` must equal the string the skill gets from Alexa.  
- **Currently:** The backend uses **Amazon account ID** (long string like `amzn1.ask.account...`) because UPS email lookup fails  
- **If UPS is configured:** The backend can use **email** instead, and you can set `alexa_user_id` to the user's email  
- **To connect an Echo to patient test002:** Edit that patient in the dashboard and set the "Email" field (alexa_user_id) to:
  - **Amazon account ID** (current method - get from logs), OR
  - **Email address** (if UPS is configured and user granted permission)  
- **Note:** The DB column is `String(50)`; the real Amazon ID is longer. If you see truncation issues, the column may need to be lengthened (e.g. migration to a longer string or text type).
