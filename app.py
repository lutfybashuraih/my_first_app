from flask import Flask

app = Flask(__name__)


# الصفحة الرئيسية: bensafy.help/
@app.route("/")
def home():
  return "Hello, World! My app is running successfully on Render."


# صفحة العملاء: bensafy.help/clients
@app.route("/clients")
def clients():
  return "هذه صفحة العملاء"


# صفحة الموظفين: bensafy.help/employees
@app.route("/employees")
def employees():
  return "هذه صفحة الموظفين"


# صفحة مدير النظام: bensafy.help/admin
@app.route("/admin")
def admin_dashboard():
  return "أهلاً بك في لوحة تحكم مدير النظام"


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=5000)
