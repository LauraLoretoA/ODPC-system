# TODO - ODPC Enquirer Type Registration + Admin Verification Enhancements

## Step 1: Database schema updates
- [ ] Update `database.py` / `enquirers` table to add:
  - `enquirer_type` (company/individual)
  - `pobox`, `location`, `county`, `kra_pin`
  - `id_number` (individual)
  - `admin_rejection_reason`
- [ ] Add safe ALTER logic so existing DBs are updated.

## Step 2: Enquirer registration page UI
- [ ] Update `Pages/enquirer_register.html`:
  - [ ] Add company/individual selector
  - [ ] Add conditional id_number field for individual
  - [ ] Add password + confirm_password
  - [ ] Add shared address/KRA fields
  - [ ] Add minimal JS for toggling + confirm password matching

## Step 3: Registration backend logic
- [ ] Update `app.py` POST `/enquirer_register`:
  - [ ] Validate confirm_password match
  - [ ] Validate required fields per enquirer_type
  - [ ] Detect duplicates:
    - [ ] If `email` already exists -> feedback: profile already exists
    - [ ] If `kra_pin` already exists -> feedback
    - [ ] If individual -> if `id_number` already exists -> feedback
  - [ ] Insert new pending enquirer.
  - [ ] Return friendly feedback.

## Step 4: Admin dashboard richer verification
- [ ] Update `app.py` GET `/admin` to query pending enquirers and render more fields.
- [ ] Add reject form UI with `rejection_reason` textarea.
- [ ] Add approval confirm prompt and feedback.

## Step 5: Admin verify/reject backend endpoints
- [ ] Update `app.py` POST `/verify_enquirer`:
  - [ ] Set `admin_verified=1`
  - [ ] Provide “approval successful”.
- [ ] Update `app.py` POST `/reject_enquirer`:
  - [ ] Store `admin_rejection_reason`
  - [ ] Keep record (do NOT delete)
  - [ ] Provide feedback + redirect back to `/admin`.

## Step 6: Verify existing login + dashboard remain functional
- [ ] Ensure enquirer login still authenticates via `enquirers.admin_verified=1`.
- [ ] Ensure enquiry submission remains functional.

## Step 7: Manual testing checklist
- [ ] Register company -> appears in admin pending.
- [ ] Register individual (with id_number) -> appears.
- [ ] Duplicate register -> show “profile already exists”.
- [ ] Admin approve -> feedback + login success.
- [ ] Admin reject -> reason stored and record remains.

