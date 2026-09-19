# Stage 2 handoff: card-tap trust and server-room access

Status: agreed design for implementation, not a claim that the components are already built. The earlier Stage 1 telemetry receiver demonstrated Pi-to-VM connectivity but will not be reused as this access API. Keep its screenshot/log as Stage 1 evidence. This document covers the Stage 2 prototype and the attack/defense evidence needed for Stage 3.

## Objective and scope

A supervisor creates a job for a technician. The technician accepts or skips it on the website. An accepted, incomplete job is the database-backed *pre-approval* for that technician to access the server room represented by one Raspberry Pi. At the site, the technician taps their registered MIFARE Classic card once. The Pi and API complete a server-challenge/HMAC exchange. If that passes and an accepted job exists, the API emails a magic link to the same technician, who is also the card's registered owner. Clicking the link approves the specific access attempt. The Pi displays the final result with LEDs. There is no confirmed physical door-lock actuator in this prototype.

This is a zero-trust-inspired access prototype: a network address, a card UID, or an accepted job alone must never open the room. Every attempt requires a fresh challenge, a valid Pi HMAC, current job authorization, and email approval. The implementation must fail closed.

## Frozen decisions

| Item | Decision |
| --- | --- |
| Room identity | The Pi's `device_id_hash` identifies the reader; its registered `room_id` is looked up in `devices`. No separate room field is sent by the Pi. |
| Card identity | The stable `card_id_hash` is the demo user's primary key. It maps directly to that person's name, email, and role. |
| Keys | One strong, static master secret is provisioned to the Pi and API through environment configuration. Three static, purpose-specific keys are derived from it. No 3 a.m. rotation. |
| Freshness | Server-issued random nonce, valid for 30 seconds and usable once. |
| Email wait | After a valid tap POST, the Pi's final GET may wait up to 120 seconds for email approval. This is *separate* from the nonce's 30-second window. |
| Magic link | The registered card owner/technician clicks an email link. Its GET approves immediately and shows a success page. This has a known email-scanner risk, documented below. |
| Pi indicators | Red steady at idle/closed; yellow blinking while in progress; green blinking after approval; red blinking on rejection/error, then red steady. |
| Transport | HMAC authenticates the request but does not encrypt it. HTTPS is required to claim confidentiality in transit. |

## System boundary and sequence

```text
Supervisor -> website/API -> SQLite: create job for technician + Pi/room
Technician -> website/API -> SQLite: accept job (or skip it)

ONE physical card tap:
PN532 -> Pi: read card UID once
Pi -> API: GET challenge, sending device_id_hash
API -> SQLite: register nonce, device binding, 30-second expiry
API -> Pi: nonce
Pi -> API: POST device_id_hash, card_id_hash, nonce, message_hmac
API: authenticate Pi, consume nonce once, match registered card,
     find accepted/incomplete job for this card and Pi/room
API -> SQLite: create PENDING attempt with 120-second deadline
API -> email: send one-time magic link to that card owner's email
API -> Pi: attempt_id + private result token
Pi -> API: GET final result, held until approval or 120-second deadline
Technician -> API: GET magic link, approving this specific attempt
API -> SQLite: atomically change PENDING -> APPROVED
API -> Pi: APPROVED; Pi blinks green

Any failed check, explicit rejection, expiry, or loss of server contact:
API/Pi -> DENIED or EXPIRED; Pi blinks red, then remains red
```

There are *three Pi-to-API calls*: challenge GET, signed-access POST, and held-result GET. The technician's email magic-link GET is a *fourth HTTP request* from a browser. Do not merge those two GET endpoints. The Pi needs the card UID only once; no second tap is required during the email wait.

## Cryptographic and identity contract

Use a randomly generated master secret of at least 32 bytes. Provision the *same bytes* to the Pi and API; do not put them in Git, screenshots, logs, browser code, or the database. A base64-encoded environment variable is a convenient transport format, but decoding must produce the original random bytes. Never treat the base64 text itself as a password chosen by a human.

Derive three keys with HMAC-SHA256 and explicit domain labels:

```text
K_device = HMAC-SHA256(master, UTF8("iot-zt:v1:device-token"))
K_card   = HMAC-SHA256(master, UTF8("iot-zt:v1:card-token"))
K_msg    = HMAC-SHA256(master, UTF8("iot-zt:v1:access-message"))

device_id_hash = lowercase_hex(HMAC-SHA256(K_device, UTF8(canonical_Pi_ID)))
card_id_hash   = lowercase_hex(HMAC-SHA256(K_card, raw_UID_bytes))
```

The API stores and looks up the resulting hashes, not the raw Pi ID or raw card UID. These two values are stable *keyed pseudonymous identifiers*, not proof that the physical card is genuine. Register their expected values during trusted setup. Both teams must agree on the exact canonical Pi ID bytes. The PN532 UID should be hashed as the exact returned bytes, not a human-formatted string with inconsistent spaces, case, or leading zeroes.

The request MAC must cover *all* signed fields, with an unambiguous byte encoding. JSON key order and whitespace are not the encoding. For version 1, use exactly:

```text
signing_bytes = UTF8(
  "access-v1\n" +
  device_id_hash + "\n" +
  card_id_hash + "\n" +
  nonce
)
message_hmac = lowercase_hex(HMAC-SHA256(K_msg, signing_bytes))
```

Validate that hashes and MAC are exactly 64 lowercase hexadecimal characters. The nonce is the exact server-issued URL-safe string and must not contain a newline. The server recomputes the MAC and compares it in constant time. Hashes and HMACs are one-way; the server does not decrypt them. If the message format changes later, use a new version label. Because room identity comes from `device_id_hash`, the device hash *must* be covered by the MAC.

The same master key on both ends is acceptable for a one-Pi demo, but compromise of the Pi exposes the secret and allows forged requests. A production design should use per-device keys in protected hardware or another stronger device identity scheme.

## HTTP API contract

All example paths are proposed names; agree on them once and keep the Pi and API implementations aligned. Return JSON for Pi-facing endpoints. Use the API's clock for all deadlines.

### 1. `GET /api/v1/challenge?device_id_hash=<64-hex>`

Request: registered `device_id_hash` only. A hash on this GET is a lookup value, *not yet authentication*. The server may issue a challenge before proving possession of the master secret, so rate-limit this endpoint and do not return device details.

Success (`200`):

```json
{"nonce":"<cryptographically-random-url-safe-value>","expires_in_seconds":30}
```

Store at least `(nonce, device_id_hash, issued_at, expires_at, consumed_at=NULL)`. Generate a new unpredictable nonce for every request. Unknown/disabled devices receive a generic error. A second challenge does not extend the first challenge's expiry.

### 2. `POST /api/v1/access-attempts`

Request (`Content-Type: application/json`):

```json
{
  "device_id_hash": "<64-hex>",
  "card_id_hash": "<64-hex>",
  "nonce": "<exact challenge nonce>",
  "message_hmac": "<64-hex>"
}
```

Process in this order: validate sizes/format; find the registered, enabled device; recompute and constant-time-check HMAC; atomically consume the nonce only if it belongs to this device, is unused, and is still within 30 seconds; find the registered card/user; find an accepted, incomplete, non-revoked job for that user and this device/room; create a pending attempt; generate and store the email approval token; queue/send email. Never treat a card hash, device hash, source IP, or nonce alone as authentication. A failed verification must not create a pending attempt or send email.

Success (`202 Accepted`):

```json
{
  "attempt_id": "<opaque-UUID>",
  "status": "PENDING_EMAIL_APPROVAL",
  "result_token": "<random-private-token-for-Pi-only>",
  "expires_in_seconds": 120
}
```

The `result_token` is delivered to the Pi only through HTTPS. Store only its hash on the server. It authorizes the Pi to read *this attempt's* result; it is not the emailed approval token. A failed check returns a rejection code and reason suitable for the Pi LED/log. Do not expose raw secrets, raw UIDs, or detailed key-check internals in public responses.

### 3. `GET /api/v1/access-attempts/{attempt_id}/result`

Pi sends `Authorization: Bearer <result_token>`. The server checks that the token belongs to this attempt and waits for an `APPROVED`, `REJECTED`, or `EXPIRED` state, no longer than the remaining 120-second deadline. Example terminal response:

```json
{"attempt_id":"<UUID>","status":"APPROVED","decision":"ACCESS_GRANTED"}
```

On deadline, return `{"status":"EXPIRED","decision":"ACCESS_DENIED"}`. A held GET is a transport convenience, not the database source of truth. The email endpoint updates SQLite; the held GET observes that state. The Pi's HTTP client timeout and any reverse-proxy timeout must exceed 120 seconds. A disconnect must not change an approved decision into an unknown open state; the Pi fails closed if it cannot obtain a valid final result.

### 4. `GET /api/v1/approve?token=<opaque-email-token>`

This is the *browser* request created by the email link. The token must be a high-entropy, one-time, expiring, opaque value bound in SQLite to one attempt and its card owner. The URL need not contain a reversible or visible user/card ID. This is a safer implementation of the requested protected identifier than encrypting a predictable ID and putting it in the URL. Store only a hash of the token. The endpoint atomically changes only that pending attempt to `APPROVED` if its 120-second deadline has not passed and the token has not been used. Then show a success page. Otherwise show a clear expired/already-used page and do not approve access.

The agreed prototype behavior is immediate approval on GET. Email gateways and link-preview systems may open GET links automatically, causing unintended approval. This is a *known security weakness*. Test and disclose it. A production design would show the attempt details on GET and require an authenticated, explicit confirmation action (POST), ideally with a stronger authenticator.

## SQLite data model

Use UTC timestamps in the database. Store `tasks` as a JSON array encoded in a SQLite `TEXT` column; validate that each item is a string before storing. Enable foreign keys on *every connection* (`PRAGMA foreign_keys=ON`) and use transactions for nonce consumption and state changes. WAL mode can help concurrent reads while the API writes, but do not hold a SQLite transaction open for the 120-second Pi GET.

| Table | Required fields and relationships |
| --- | --- |
| `users` | `card_id_hash TEXT PRIMARY KEY`, `full_name TEXT`, `email TEXT`, `role TEXT` (`supervisor` or `technician`), `active INTEGER`. The card hash is the demo user ID; the owner's email is on this row. |
| `devices` | `device_id_hash TEXT PRIMARY KEY`, `room_id TEXT UNIQUE`, `active INTEGER`, optional display name. The Pi hash resolves to one server room. |
| `jobs` | `job_id TEXT PRIMARY KEY`, `created_at`, `supervisor_id REFERENCES users(card_id_hash)`, `technician_id REFERENCES users(card_id_hash)`, `device_id_hash REFERENCES devices(device_id_hash)`, `tasks_json TEXT`, `status TEXT`, `is_complete INTEGER`, `accepted_at`, optional `completed_at`/`revoked_at`. Status: `pending`, `accepted`, `skipped`, `completed`, `revoked`. Enforce `is_complete=1` iff status is `completed`, or remove the redundant flag in a later revision. |
| `challenges` | `nonce TEXT PRIMARY KEY`, `device_id_hash REFERENCES devices`, `issued_at`, `expires_at`, `consumed_at`. Periodically prune old rows after audit retention needs are met. |
| `access_attempts` | `attempt_id TEXT PRIMARY KEY`, `device_id_hash`, `card_id_hash`, `job_id`, `status`, `created_at`, `expires_at`, `decided_at`, `result_token_hash`, and a safe reason code. Status: `PENDING_EMAIL_APPROVAL`, `APPROVED`, `REJECTED`, `EXPIRED`. Snapshot the matched job and identities so the audit trail explains each decision. |
| `approval_links` | `token_hash TEXT PRIMARY KEY`, `attempt_id REFERENCES access_attempts`, `created_at`, `expires_at`, `used_at`. A token can approve only its own attempt. |
| `audit_events` | `event_id`, timestamp, attempt ID if present, device hash, card hash if known, event type, outcome/reason code, and source metadata. Do not log master/derived keys, raw UID, HMAC inputs, full email token, or result token. |

Acceptance is the pre-approval recorded in the `jobs` row. A job is eligible only when `status='accepted'`, `is_complete=0`, the user/device match, and no revocation or expiry applies. No job-access time window beyond this was specified for the demo; document this as a limitation. For production, add explicit `valid_from` and `valid_until` policy fields. If multiple accepted jobs match, choose one deterministically and record its ID on the access attempt.

Only authorized website sessions may create jobs, accept/skip them, mark them complete, or revoke them. A technician must not be able to accept a job on someone else's behalf. Role checks must happen server-side, regardless of which dashboard buttons are visible.

## Pi state machine and LEDs

| State | Indicator | Transition |
| --- | --- | --- |
| `IDLE_CLOSED` | Red steady | Card tap -> `CHALLENGE_PENDING`. |
| `CHALLENGE_PENDING` | Yellow blinking | Obtain nonce within request timeout, then submit POST before its 30-second expiry. |
| `VERIFYING` | Yellow blinking | Rejected -> `DENIED`; `202 PENDING` -> `AWAITING_EMAIL`. |
| `AWAITING_EMAIL` | Yellow blinking | Hold result GET; approval -> `APPROVED`; expiry/rejection/network failure -> `DENIED`. |
| `APPROVED` | Green blinking | Show approved/open indication for a short configured interval, then return to red steady. No actual lock actuation is specified. |
| `DENIED` | Red blinking, then red steady | Log a safe reason code and return to `IDLE_CLOSED`. |

Do not start a second access attempt while one is pending unless the first is explicitly cancelled/expired. Never turn green after a request timeout, malformed response, lost network, or merely receiving a nonce. If the API response is approved but for a different `attempt_id`, deny it. Keep UID values and keys out of serial debug logs.

## Timing, concurrency, and failure rules

- Nonce lifetime: 30 seconds from server issuance; the server alone decides expiry. It must be consumed atomically, so two simultaneous copies of a POST cannot both pass.
- Email approval lifetime: 120 seconds from creation of the pending attempt, independent of nonce expiry. A nonce can expire after its POST was accepted without cancelling an already pending email attempt.
- The held result GET must not hold a SQLite write lock or a server worker thread for the whole period. An asynchronous wait with periodic database checks or a notification mechanism is suitable for this prototype. Configure the Pi and any proxy timeouts accordingly.
- Approval and expiry are competing state transitions. Exactly one should win atomically; once terminal, a later click cannot reverse the decision.
- If email delivery fails, mark the attempt rejected/expired rather than leaving it pending indefinitely. If the Pi loses its connection, its LED must remain/return red until it obtains a valid final result.
- Limit challenge requests, malformed HMAC attempts, email sends, and active pending attempts per device/card to reduce abuse.

## Security test matrix and evidence

Save a timestamped screenshot or log excerpt for each test. Evidence should show the Pi request or simulated request, server decision, database/audit event, and LED/dashboard state where practical. Never publish the master secret or live magic tokens.

| Test | Expected result |
| --- | --- |
| Valid registered device + card, accepted job, email owner clicks before deadline | Pending yellow, then approved green; one audit trail tied to the job and attempt. |
| Registered card with no job, pending job, skipped job, completed job, or wrong device/room | Denied before email is sent; red LED. |
| Alter one byte of `card_id_hash`, `device_id_hash`, or nonce after calculating `message_hmac` | HMAC or nonce/device binding fails; no pending attempt. |
| Use unknown device hash or unknown card hash | Denied; no email and no green LED. |
| Replay the exact valid POST or submit two copies at once | Only the first can consume the nonce; all others rejected. |
| Submit the POST after 30 seconds or with a nonce issued for another Pi | Rejected; no email. |
| Use wrong master secret on Pi, wrong derived-key label, or inconsistent UID byte formatting | Rejected; diagnose as integration mismatch without logging secrets. |
| Approve email after 120 seconds or click the same link twice | Cannot change a terminal attempt or trigger a second approval. |
| Try email token from attempt A against attempt B | Cannot approve B. |
| Forge a Pi result GET with a guessed attempt ID but no correct `result_token` | Unauthorized; no final decision leaked. |
| Disconnect Pi, stop API, or interrupt email delivery mid-attempt | Fail closed; no green LED; reason/timeout recorded. |
| Email link scanner opens the approval URL before the user | *Known prototype failure:* may approve immediately. Demonstrate or explain it honestly; production fix is confirmation POST plus stronger user authentication. |
| Clone or emulate a MIFARE Classic UID | *Known limitation:* hash/HMAC authenticates the Pi's report, not the physical card. Email approval and job policy reduce impact but do not make the card unclonable. |
| Observe traffic on HTTP rather than HTTPS | *Known limitation:* identifiers and tokens can be visible; HMAC does not encrypt. Use HTTPS before claiming network confidentiality. |
| Compromise the Pi's master secret | *Known limitation:* attacker can forge valid requests. Production requires per-device protected keys and revocation. |

For the hackathon, the strongest Stage 2 proof is a paired demonstration: the same valid request succeeds once, while a tampered or replayed request is rejected. For Stage 3, show at least one attack, its audit record, the red/closed response, and that a fresh legitimate attempt still works. The handbook accepts screenshots, logs, terminal output, diagrams, code/config excerpts, and dashboard screenshots as evidence.

## Open implementation choices, not new requirements

- Exact route names and JSON error codes can change, but both sides must share one written contract.
- Choose the initial registration procedure for stable card/device hashes; the database cannot infer a raw UID from a stored hash.
- Choose the Pi's approved-indication duration and email delivery provider. No physical door mechanism has been specified.
- Decide whether the prototype has HTTPS available. If it remains HTTP on the local VM, state the confidentiality limitation explicitly.
- Decide how email links are protected against automatic link scanning if the team later changes the agreed immediate-GET behavior.

## Reference material

- [Handbook Stage 2 and Stage 3 transcription](transcriptions/Operation%20Zero%20Trust%20Handbook%20Mission.md)
- [Submission evidence and judging focus](transcriptions/Submission%20Evidence%20and%20Judging%20Focus.md)
- [NIST Zero Trust Architecture](https://csrc.nist.gov/pubs/sp/800/207/final)
- [OWASP Transaction Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html)
- [OWASP guidance for random, single-use, expiring URL tokens](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html)

Terminology for the presentation: call this *email-based owner approval*, not standards-grade email 2FA. NIST does not accept email as an out-of-band authentication factor for higher-assurance authentication. This prototype also does not cryptographically authenticate the MIFARE Classic card itself.
