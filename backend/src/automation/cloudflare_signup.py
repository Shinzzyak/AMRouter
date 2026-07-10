import sys, subprocess, time, random, os

# Priority 1: Webshare authenticated proxies (paid, high quality)
WEBSHARE_FILE = '/root/.openclaw/workspace/.secrets/webshare_proxies.txt'
# Priority 2: validated free proxies (fallback)
FREE_FILE = '/root/.openclaw/workspace/proxy-scraper/alive_proxies.txt'
CORE_SCRIPT = '/root/.openclaw/workspace/AMRouter/backend/src/automation/cloudflare_signup_core.py'


def load_webshare():
    """Parse Webshare list: IP:PORT:USER:PASS -> socks5://user:pass@ip:port"""
    out = []
    try:
        with open(WEBSHARE_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(':')
                if len(parts) < 4:
                    continue
                ip, port, user, pwd = parts[0], parts[1], parts[2], parts[3]
                # Camoufox (Firefox/Playwright) does NOT support socks5 auth;
                # use http:// scheme which supports username/password.
                out.append({
                    'server': f'http://{ip}:{port}',
                    'user': user,
                    'pass': pwd,
                })
    except Exception as e:
        print(f"[webshare] load error: {e}", flush=True)
    return out


def load_free():
    """Parse free validated proxies (format: protocol://ip:port)"""
    out = []
    try:
        with open(FREE_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append({'server': line, 'user': None, 'pass': None})
    except Exception:
        pass
    return out


def main():
    args = sys.argv[1:]

    # Strip any proxy args Node.js injected (we choose our own)
    clean_args = [
        a for a in args
        if not (a.startswith('--proxy-server') or a.startswith('--proxy-user') or a.startswith('--proxy-pass'))
    ]

    proxies = load_webshare()
    if not proxies:
        print("[warn] No Webshare proxies loaded, falling back to free pool", flush=True)
        proxies = load_free()
    else:
        print(f"[proxy] Using {len(proxies)} Webshare proxies", flush=True)

    if not proxies:
        print('{"step": "FATAL", "error": "No proxies available at all."}', flush=True)
        sys.exit(1)

    random.shuffle(proxies)
    max_retries = min(len(proxies), 10)
    used = set()

    for attempt in range(max_retries):
        cmd = [sys.executable, CORE_SCRIPT] + clean_args

        # Pick unused proxy
        proxy = None
        for p in proxies:
            key = p['server']
            if key not in used:
                proxy = p
                used.add(key)
                break

        if not proxy:
            print(f"--- Attempt {attempt+1}: no more unique proxies ---", flush=True)
            break

        cmd.append(f"--proxy-server={proxy['server']}")
        if proxy['user']:
            cmd.append(f"--proxy-user={proxy['user']}")
        if proxy['pass']:
            cmd.append(f"--proxy-pass={proxy['pass']}")

        # redact creds in log
        print(f"--- Attempt {attempt+1}/{max_retries} | Proxy: {proxy['server']} ---", flush=True)

        proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
        proc.wait()

        if proc.returncode == 0:
            sys.exit(0)
        elif proc.returncode == 2:
            print("Fatal argparse error (code 2), aborting.", flush=True)
            sys.exit(2)
        else:
            print(f"Attempt {attempt+1} failed (code {proc.returncode}). Trying next proxy...", flush=True)
            time.sleep(2)

    print('{"step": "FATAL", "error": "All proxy attempts failed."}', flush=True)
    sys.exit(1)


if __name__ == "__main__":
    main()
