from sentinel_gui import app


@app.route('/')
@app.route('/index')
def index():
    return "Hello, World!"
