import http.cookiejar
import instaloader

COOKIE_FILE = "www.instagram.com_cookies.txt"# bu yerga o'z fayl nomingizni yozing
USERNAME_HINT = "tojimatovxikmatilla"

jar = http.cookiejar.MozillaCookieJar(COOKIE_FILE)
jar.load(ignore_discard=True, ignore_expires=True)

L = instaloader.Instaloader()
L.context._session.cookies.update(jar)

username = L.test_login()

if username:
    L.context.username = username
    session_filename = f"session-{username}.session"
    L.save_session_to_file(session_filename)
    print(f"\nMuvaffaqiyatli! Sessiya fayli yaratildi: {session_filename}")
else:
    print("\nLogin aniqlanmadi. Cookie fayl eskirgan yoki noto'g'ri bo'lishi mumkin.")