from flask import Flask, flash, request, redirect, render_template, url_for
import shutil
from werkzeug import secure_filename
import sys
import subprocess
import os
from flask_httpauth import HTTPDigestAuth

app = Flask(__name__, instance_relative_config=True)
app.config.from_object('config')
app.config.from_pyfile('config.py', silent=True)

ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])
auth = HTTPDigestAuth()

@auth.get_password
def get_pw(username):
    if username == app.config['USERNAME']:
        return app.config['PASSWORD']
    return None

@app.route('/')
@auth.login_required
def home():
    return render_template('index.html')

@app.route('/images')
@auth.login_required
def images():
    return render_template('images.html')

@app.route('/browse')
@auth.login_required
def browse():
    return render_template('browse.html')

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

@app.route('/image/post', methods=['POST'])
@auth.login_required
def upload_image():
    if request.method == 'POST':
        try :
            file = request.files['file']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(filename)
                #file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                #return redirect(url_for('uploaded_file', filename=filename))
                flash('Success - Image uploaded')
                return redirect(url_for('images'))
        except :
            flash('Failed - Uploading image')
            return redirect(url_for('images'))

def valid_login(request):
    if username == app.config['USERNAME'] and password == app.config['PASSWORD'] :
        return True
    else :
        return False

@app.route('/content/post',  methods=['POST'])
@auth.login_required
def make_post():
    title = request.form['title']
    post = request.form['post']
    typeFile = request.form['extension']
    message = write_post(title, typeFile, post)
    flash(message)
    return redirect(url_for('home'))

@app.route('/content/postna',  methods=['POST'])
def make_postna():
    # Make a post from the server, save it to markdown format.
    if valid_login(request):
        print("valid login")
        title = request.form['title']
        post = request.form['post']
        typeFile = request.form['extension']
        return write_post(title, typeFile, post)
    else:
        title = "Failed"
        post = "None"
        return '{{ "status" : "{0}", "message" : "{1}"  }}'.format("failed", "invalid credentials")

def write_post(title, typeFile, post) :
    try :
        title = secure_filename(title)
        title = os.path.splitext(title)[0] + "." + typeFile
        print title
        fd = open(title, 'wb')
        fd.write(post)
        fd.close()
    except :
        print("unable to write the file")
        return '{{ "status" : "{0}", "message" : "{1}"  }}'.format("failed", "unable to write the file \n" + str(sys.exc_info()[0]))
    try :
        shutil.move(title, os.path.join(app.config['PELICAN_PATH'], app.config['PELICAN_CONTENT']))
        exitVal = subprocess.call(["make", "-C", app.config['PELICAN_PATH'], "html"])
        print exitVal
        copytree(os.path.join(app.config['PELICAN_PATH'],app.config['PELICAN_OUTPUT']), OUTPUT_DIR)
        print "copy done"
    except :
        print("Exception in moving content")
        print(sys.exc_info())
        return '{{ "status" : "{0}", "message" : "{1}"  }}'.format("failed", "Exception in moving content \n" + str(sys.exc_info()[0]))
    return '{{ "status" : "{0}", "message" : "{1}"  }}'.format("success", "")

def copytree(src, dst, symlinks=False, ignore=None):
    if not os.path.exists(dst):
        os.makedirs(dst)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            copytree(s, d, symlinks, ignore)
        else:
            if not os.path.exists(d) or os.stat(s).st_mtime - os.stat(d).st_mtime > 1:
                shutil.copy2(s, d)

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=app.config['PORT'])
