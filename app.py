from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Hello, World! My app is running successfully on Render."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
