import sys, subprocess, os, urllib2, shutil, re
from flask import Flask, flash, request, redirect, render_template, url_for, g, jsonify
from werkzeug import secure_filename
from flask_httpauth import HTTPDigestAuth
from tinydb import TinyDB, Query
from urlparse import urlparse

app = Flask(__name__, instance_relative_config=True)
app.config.from_object('config')
app.config.from_pyfile('config.py', silent=True)

ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])
auth = HTTPDigestAuth()
USER_TABLE = "user_table"
PELICAN_THEME_TABLE = "pelican_theme_table"

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
APP_STATIC = os.path.join(APP_ROOT, 'static')

def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'app_db'):
        g.app_db = TinyDB('db.json')
    return g.app_db


@app.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'app_db'):
        g.app_db.close()

@auth.get_password
def get_pw(username):
    if username == app.config['USERNAME']:
        return app.config['PASSWORD']
    return None

@app.route('/admin')
@auth.login_required
def admin():
    return render_template('admin.html')

@app.route('/admin/images')
@auth.login_required
def images():
    return render_template('images.html')

@app.route('/admin/browse')
@auth.login_required
def browse():
    return render_template('browse.html')

@app.route('/admin/settings')
@auth.login_required
def settings():
    return render_template('settings.html')

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

@app.route('/admin/image/post', methods=['POST'])
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

@app.route('/admin/content/post',  methods=['POST'])
@auth.login_required
def make_post():
    title = request.form['title']
    post = request.form['post']
    typeFile = request.form['extension']
    message = write_post(title, typeFile, post)
    flash(message)
    return redirect(url_for('admin'))

@app.route('/admin/content/postna',  methods=['POST'])
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

"""
@app.route('/admin/save_settings', methods=['POST'])
@auth.login_required
def save_settings():
    title = request.form['title']
    post = request.form['post']
    typeFile = request.form['extension']
    message = write_post(title, typeFile, post)
    flash(message)
"""

@app.route('/admin/get_pelican_themes')
@auth.login_required
def getPelicanThemes():
    db = get_db();
    table = db.table(PELICAN_THEME_TABLE)
    if len(table) == 0 :
        get_themes()
    themes = table.all()
    return jsonify(themes = themes)


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

def read_themes_file():
    with open("pelican_themes", "r") as f :
        db = get_db();
        theme_table = db.table(PELICAN_THEME_TABLE)
        while True :
            line1 = f.readline()
            line2 = f.readline()
            line3 = f.readline()
            #print line1, line2
            if not line3 : break
            module_match = re.match("\[submodule\s+\"(.+)\"\]", line1)
            if module_match :
                theme_name = module_match.group(1)
                #this is not a theme
                if theme_name == "pelicanthemes-generator" :
                    continue
            else :
                continue
            url_match = re.match("\s*url\s+=\s+(\S+).*", line3)
            if url_match :
                url = url_match.group(1)
            else :
                continue
            #themes[theme_name] = url
            theme_table.insert({"name" : theme_name, "url" : url})

@app.route('/admin/update_pelican_themes')
@auth.login_required
def get_themes():
    response = urllib2.urlopen("https://raw.githubusercontent.com/getpelican/pelican-themes/master/.gitmodules")
    with open('pelican_themes','w') as output:
        output.write(response.read())
    read_themes_file()

"""
def sync_settings():
    db = get_db()
    table = db.table(USER_TABLE)
    user = Query()
    user_pref = db.search(user.user_name == app.config["USERNAME"])
    if user_pref["site_generator"].lower() == "pelican" :
        if not os.path.exists("./site_content") :
            if user_pref.use_git :
                exitVal = subprocess.call(["git", "clone", user_pref.git_repo , "site_content"])
"""

def get_theme_repo(theme_url) :
    db = get_db()
    theme_table = db.table(PELICAN_THEME_TABLE)
    theme_query = Query()
    theme_res = theme_table.search(theme_query.url == theme_url)
    if len(theme_res) < 1 :
        return
    theme_url = theme_res[0]["url"]
    os.chdir(APP_ROOT)
    if not os.path.exists("./theme"):
        os.mkdir("./theme")
    os.chdir("./theme")
    exitVal = subprocess.call(["git", "clone", theme_url])
    git_path = urlparse(theme_url).path
    repo_name = git_path[ git_path.rfind("/") + 1: ]
    repo_name = repo_name[  : repo_name.find(".git") ]
    os.chdir(repo_name)
    exitVal = subprocess.call(["git", "pull"])


@app.route('/admin/save_settings', methods=['POST'])
@auth.login_required
def save_settings():
    print "save_settings"
    site_generator = request.form['site_generator']
    #use_git = request.form['use_git']
    #git_repo = request.form['git_repo']
    #git_username = request.form['git_username']
    #git_password = request.form['git_password']
    theme = request.form['theme']

    db = get_db()
    table = db.table(USER_TABLE)
    user_pref = { "user_name" : app.config["USERNAME"], "site_generator" : site_generator,
                "theme" : theme}
    """
    "use_git" : use_git,
    "git_repo" : git_repo, "git_username" : git_username, "git_password" : git_password,
    """
    table.insert(user_pref)
    print theme
    get_theme_repo(theme)
    message  = '{{ "status" : "{0}", "message" : "{1}"  }}'.format("success", "")
    flash(message)
    return redirect(url_for('settings'))
    #return write_post(title, typeFile, post)

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=app.config['PORT'], debug=True)
