from flask import Flask, redirect, url_for, abort, render_template, request, jsonify
from flask_oauth2_login import GoogleLogin
from flask_login import LoginManager, login_required, login_user
from itsdangerous import TimedSerializer, BadTimeSignature
import datetime
import pyqrcode
import urllib
import os
import io
import re

app = Flask(__name__)
app.secret_key = os.environ['FLASK_SECRET_KEY']
app.config['GOOGLE_LOGIN_CLIENT_ID'] = os.environ['GOOGLE_LOGIN_CLIENT_ID']
app.config['GOOGLE_LOGIN_CLIENT_SECRET'] = os.environ['GOOGLE_LOGIN_CLIENT_SECRET']
app.config['GOOGLE_LOGIN_REDIRECT_SCHEME'] = os.environ['GOOGLE_LOGIN_REDIRECT_SCHEME']
app.config['GOOGLE_LOGIN_SCOPE'] = 'email'

google = GoogleLogin(app)
login_manager = LoginManager()
login_manager.init_app(app)
serializer = TimedSerializer(os.environ['FLASK_SECRET_KEY'])

accepted_emails = re.compile(os.environ['ACCEPTED_EMAILS_REGEX'])
redirect_url = os.environ['REDIRECT_URL']
id_file = os.environ['ID_FILE_PATH']

print os.environ['ACCEPTED_EMAILS_REGEX']


@app.route("/")
@login_required
def index():
    try:
        # yes, I'm saving the id on a text file... I've heard about other approaches using specialized
        # systems to store data, but I'm the only one that's ever going to use this!
        with open(id_file, 'r') as f:
            last = int(f.read())
    except:
        last = 0

    request = last + 1
    token = serializer.dumps(request)
    url = pyqrcode.create(redirect_url.replace('__token__', urllib.quote(token)))

    buffer = io.BytesIO()
    url.svg(buffer)
    svg = buffer.getvalue()

    # hacky hack to make the svg size CSS adjustable in a non hacky way... hacky python > hacky CSS
    width = re.search('width="([0-9]+)"', svg).group(1)
    height = re.search('height="([0-9]+)"', svg).group(1)
    svg = re.sub('((height)|(width))="[0-9]+" ', '', svg)
    svg = svg.replace('<svg', '<svg viewBox="0 0 %s %s"' % (width, height))

    return render_template('index.html', qrcode=svg, token=token, when=datetime.datetime.utcnow())


@app.route("/get-new-badge")
@login_required
def get_new_badge():
    try:
        with open(id_file, 'r') as f:
            last = int(f.read())
    except:
        last = 0

    request = last + 1
    with open(id_file, 'w') as ff:
        ff.write(str(request))

    return redirect(url_for('index'))


@app.route("/check")
@login_required
def check():
    try:
        id, timestamp = serializer.loads(request.args.get('token'), return_timestamp=True)
        return '%s %s' % (id, timestamp)
    except BadTimeSignature:
        return 'Bad signature'


##
## Google authentication (and Flask_Login) setup ##
##
@login_manager.user_loader
def load_user(user_id):
    if accepted_emails.match(user_id):
        return User(user_id)
    return None

login_manager.login_view = 'login'


@app.route('/login')
def login():
    return redirect(google.authorization_url())


@google.login_success
def login_success(token, userinfo):
    if accepted_emails.match(userinfo['email']):
        login_user(User(userinfo['email']))
        return redirect(url_for('index'))
    abort(401)


@google.login_failure
def login_failure(e):
    print jsonify(error=str(e))
    return 'Ouch!'


class User(object):
    def __init__(self, user_id=None):
        self.user_id = user_id

    def is_active(self):
        return self.user_id is not None

    def is_authenticated(self):
        return self.user_id is not None

    def is_anonymous(self):
        return self.user_id is None

    def get_id(self):
        return self.user_id
