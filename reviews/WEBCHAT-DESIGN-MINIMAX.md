**Key pitfalls to dodge**

- **Weak or exposed secret** – “random mode‑600 password” must be *cryptographically random* (≥ 128 bits) and stored in a system key‑chain, not a world‑readable config file.  
- **Predictable session tokens** – generate HttpOnly, SameSite Strict cookies with `secrets.token_urlsafe(32)`; reuse or short tokens invite fixation attacks.  
- **Allow‑list bypass** – normalise and compare Host/Origin *exactly* (case‑fold, strip trailing dot). A single missing check can let an attacker’s site slip through.  
- **CSRF token reuse** – issue a per‑session, per‑request token; validate on every POST/PUT/DELETE, and reject if missing or reused.  
- **Non‑atomic file I/O** – polling a JSON file without file locking (e.g., `fcntl.flock`) can corrupt state when multiple workers read/write simultaneously. Use a write‑ahead log or a transactional store.  
- **Idempotency without persistence** – store idempotency IDs server‑side (e.g., Redis) and reject duplicate submissions; client‑supplied IDs alone are not enough.  
- **Process‑group leakage** – child processes spawned for replies should be placed in a *new* process group (`setpgid`) and have a hard resource limit (CPU, memory) to prevent runaway jobs from affecting the server.  
- **Unsafe restart logic** – interrupting a pending reply without cleaning up its state can leave “dangling” entries; always transition through a defined *cancelled* state and log the cancellation.  
- **Credential forwarding in fallbacks** – passing the user’s ChatGPT/Copilot token to `Cursor`, `bin/ask-gemini.sh`, etc., can leak the token; authenticate each downstream CLI separately and never embed long‑lived secrets in scripts.  
- **Unenforced “never automatic” constraint** – the rule “Claude never automatic” must be enforced by a server‑side permission check, not a comment or client‑side flag.  
- **Missing route authentication** – status/review/jobs endpoints are often assumed “safe”; protect them with the same session validation used for mutations.  
- **Path‑traversal on file routes** – even fixed routes that serve static files must validate the requested path (e.g., `os.path.realpath` and prefix check) to avoid accidental disclosure of `../`.  
- **No rate‑limiting / request‑size caps** – an unbounded poll endpoint can be turned into a cheap DoS vector; add per‑IP and per‑session limits.  
- **Incorrect file permissions** – mode 600 alone isn’t enough; ensure the directory containing the file also restricts access (e.g., `0700`) and that the process runs under a dedicated user.  
- **launchd/screen naming collisions** – use a deterministic, unique session name (e.g., based on the user’s UUID) and verify the screen session isn’t already running before spawning.  
- **Accidental secret leakage in logs** – mask or omit passwords, tokens, and CSRF values from any logging or error messages.  

Avoiding these concrete mistakes keeps the local “Bob” service sound: strong authentication, strict CSRF protection, atomic state handling, isolated execution environments, and disciplined secret management.
