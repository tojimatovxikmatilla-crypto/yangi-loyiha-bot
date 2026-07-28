import instaloader
import getpass

username = input("Instagram username: ")
password = getpass.getpass("Password: ")

L = instaloader.Instaloader()

try:
    L.login(username, password)
except instaloader.TwoFactorAuthRequiredException:
    code = input("2FA kod (agar so'ralsa): ")
    L.two_factor_login(code)

session_filename = f"session-{username}.session"
L.save_session_to_file(session_filename)
print(f"\nSessiya fayli yaratildi: {session_filename}")