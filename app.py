# -*- coding: utf8 -*-
import os
import datetime
import shutil
import uuid
import zipfile
from flask import g, Flask, flash, send_from_directory, session, url_for, redirect, request, render_template
from werkzeug.utils import secure_filename
from flask_uploads import UploadSet, configure_uploads, IMAGES, UploadNotAllowed
from flaskext.couchdb import CouchDBManager, Document, TextField, DateTimeField, ViewField, BooleanField

UPLOADED_VIDEOS_DEST = 'uploads'
DEBUG = True

ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = '123456'

COUCHDB_SERVER = 'http://127.0.0.1:5984/'
COUCHDB_DATABASE = 'videocms'

app = Flask(__name__)
app.config.from_object(__name__)
#app.config.from_envvar('VIDEO_SETTINGS', silent=False)
app.secret_key = os.urandom(24)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024 * 1024

EXTENSIONS = ('mp4', 'MP4', '3gp', '3GP', 'ts', 'TS', 'zip', 'f4v', 'F4V', 'm4v', 'M4V', 'mov', 'MOV');
#videos = UploadSet('videos', extensions=EXTENSIONS, default_dest=lambda app: UPLOADED_VIDEOS_DEST)
videos = UploadSet('videos', extensions=EXTENSIONS)

configure_uploads(app, videos)

class Post(Document):
    doc_type = 'post'
    title = TextField()
    filename = TextField()
    caption = TextField()
    url = TextField()
    is_folder = BooleanField(default=False)
    published = DateTimeField(default=datetime.datetime.utcnow)
    all = ViewField('post', '''\
            function(doc) {
                if (doc.doc_type == 'post') 
                    emit(doc.published, doc);
            }''')

dbmanager = CouchDBManager()
dbmanager.add_document(Post)
dbmanager.setup(app)

def unique_id():
    return hex(uuid.uuid4().time)[2: -1]

def goto_index():
    return redirect(url_for('index'))

def goto_notfound():
    return "404"

@app.before_request
def login_handle():
    session.permanent = True
    app.permanent_session_lifetime = datetime.timedelta(minutes=20)
    g.logged_in = bool(session.get('logged_in'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):
        flash("You are already logged in")
        return goto_index()
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if (username == app.config['ADMIN_USERNAME'] and 
            password == app.config['ADMIN_PASSWORD']):
            session['logged_in'] = True
            flash("Successfully logged in")
            return goto_index()
        else:
            flash("Invalid Username or Password")
    return render_template('login.html')

@app.route('/logout')
def logout():
    if session.get('logged_in'):
        session['logged_in'] = False
        flash("Successfully logged out")
    else:
        flash("You are not logged in")
    return goto_index()

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    posts = Post.all()
    return render_template('index.html', posts=posts)

def processZipfile(filename):
    print "Uploaded a zip file, unzip it"
    zip_ref = zipfile.ZipFile(videos.path(filename), 'r')
    zip_ref.extractall(app.config['UPLOADED_VIDEOS_DEST'])
    zip_ref.close()
    os.remove(os.path.abspath(videos.path(filename))) 

def isZipfile(filename):
    return filename.split(".")[-1] == "zip"

@app.route('/new', methods=['GET', 'POST'])
def new():
    flash(u'HLS 文件上传要求：')
    flash(u'新建与视频文件名同名的文件夹')
    flash(u'M3U8 文件的命名必须与视频文件名相同')
    flash(u'将所有 TS 文件以及 m3u8 文件放入上述文件夹')
    flash(u'将文件夹打包成 zip 格式，命名与视频文件名相同，并以 .zip 为后缀名')
    if request.method == 'POST':
        uploaded_file = request.files.get('video')
        title = request.form.get('title')
        caption = request.form.get('caption')
        if not (uploaded_file and title and caption):
            flash(u'你需要把所有的字段都填充完整')
        else:
            try:
                filename = videos.save(uploaded_file)
                if isZipfile(filename):
                    processZipfile(filename)
                print videos.url(filename)
                print videos.path(filename)
            except UploadNotAllowed:
                flash(u'上传文件格式错误')
                flashmessage = u'你只能上传以' + str(EXTENSIONS) + u'后缀的文件'
                flash(flashmessage)
            else:
                if isZipfile(filename):
                    file_url = videos.url(filename)
                    video_name = "".join(filename.rsplit(".zip", 1))
                    video_url = "".join(file_url.rsplit(".zip", 1)) + "/" + video_name + ".m3u8"
                    post = Post(title=title, caption=caption, filename=video_name, url=video_url, is_folder=True)
                    post.id = unique_id()
                    post.store()
                else:
                    post = Post(title=title, caption=caption, filename=filename, url=videos.url(filename))
                    post.id = unique_id()
                    post.store()
                flash("Post successful")
        return redirect(url_for('index'))
    return render_template('new.html')

@app.route('/detail/<post_id>', methods=['GET', 'POST'])
def detail(post_id):
    post = Post.load(post_id)
    if not post:
        goto_notfound()
    return render_template('detail.html', post=post)

@app.route('/delete/<post_id>', methods=['GET', 'POST'])
def delete(post_id):
    post = Post.load(post_id)
    if not post:
        goto_notfound()
    if post.is_folder:
        shutil.rmtree(os.path.abspath(videos.path(post.filename)))
    else:
        os.remove(os.path.abspath(videos.path(post.filename)))
    g.couch.delete(post)
    return goto_index()

@app.route('/about')
def about():
    return render_template('about.html', about='Video CMS V0.1')

if __name__ == '__main__':
    app.run(debug=True, threaded=True, host='0.0.0.0', port=40000)
