import sys, subprocess, os, urllib.request, urllib.error, urllib.parse, shutil, re
from flask import Flask, flash, request, redirect, render_template, url_for, g, jsonify
from werkzeug import secure_filename
from flask_httpauth import HTTPDigestAuth
from urllib.parse import urlparse
from sqlite3 import dbapi2 as sqlite3
import json

app = Flask(__name__, instance_relative_config=True)
app.config.from_object('config')
app.config.from_pyfile('config.py', silent=True)

ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])
auth = HTTPDigestAuth()
USER_TABLE = "user_table"
PELICAN_THEME_TABLE = "pelican_theme_table"

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
APP_STATIC = os.path.join(APP_ROOT, 'static')
DATABASE =  APP_ROOT + "./thingari.db"

def connect_db():
    """Connects to the specific database."""
    print("connecting to the db")
    rv = sqlite3.connect(DATABASE)
    rv.row_factory = sqlite3.Row
    return rv

@app.cli.command()
def init_db():
    """Initializes the database."""
    db = connect_db()
    with app.open_resource('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()

def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db

@app.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    print("Closing the db")
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

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
            flash('Failed - Uploading image', 'error')
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
def get_pelican_themes():
    db = get_db();
    cur = db.execute('select theme, url from %s' % (PELICAN_THEME_TABLE))
    themes = cur.fetchall()

    if len(themes) == 0 :
        get_themes()
        cur = db.execute('select theme, url from %s' % (PELICAN_THEME_TABLE))
        themes = cur.fetchall()
    print((type(themes)))
    themes_list = []
    for t in themes :
        d = {}
        d["url"] = t["url"]
        d["theme"] = t["theme"]
        themes_list.append(d)
    #print(themes)
    return jsonify(themes=themes_list)


def write_post(title, typeFile, post) :
    try :
        title = secure_filename(title)
        title = os.path.splitext(title)[0] + "." + typeFile
        print(title)
        fd = open(title, 'wb')
        fd.write(post)
        fd.close()
    except :
        print("unable to write the file")
        flash("unable to write te file", "error")
        return '{{ "status" : "{0}", "message" : "{1}"  }}'.format("failed", "unable to write the file \n" + str(sys.exc_info()[0]))
    try :
        print("Moving file")
        shutil.move(title, os.path.join(app.config['PELICAN_PATH'], app.config['PELICAN_CONTENT']))
        print(("Running make " + get_theme_dir()))
        os.chdir(app.config['PELICAN_PATH'])
        exitVal = subprocess.call(["pelican", "-t", "../theme/" + get_theme_dir(), "-o", "../html"])
        print(("Exit val " + str(exitVal)))

        os.chdir(APP_ROOT)

        if not os.path.exists(app.config['OUTPUT_DIR']) :
            os.mkdir(app.config['OUTPUT_DIR'])
        copytree(os.path.join(app.config['PELICAN_PATH'],app.config['PELICAN_OUTPUT']), app.config['OUTPUT_DIR'])
        print("copy done")
    except :
        print("Exception in moving content")
        print((sys.exc_info()))
        flash("Problem in moving content " + str(sys.exc_info()[0]) , "error")
        return '{{ "status" : "{0}", "message" : "{1}"  }}'.format("failed", "Exception in moving content \n" + str(sys.exc_info()[0]))
    return '{{ "status" : "{0}", "message" : "{1}"  }}'.format("success", "")

def copytree(src, dst, symlinks=False, ignore=None):
    if not os.path.exists(dst):
        os.makedirs(dst)
    if not os.path.exists(src):
        print(("Source directory %s not present" %(src)))
        return
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
        db.execute("delete from %s" %(PELICAN_THEME_TABLE))
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
            db.execute( "insert into pelican_theme_table (theme, url) values (?, ?) ", [theme_name, url] )
        db.commit()

@app.route('/admin/update_pelican_themes')
@auth.login_required
def get_themes():
    try :
        response = urllib.request.urlopen("https://raw.githubusercontent.com/getpelican/pelican-themes/master/.gitmodules")
        with open('pelican_themes','wb') as output:
            output.write(response.read())
        read_themes_file()
    except:
        flash("Unable to get the theme file \n" + str(sys.exc_info()[0]), "error")

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

def get_dir_from_repo(theme_url) :
    git_path = urlparse(theme_url).path
    #print(git_path)
    repo_name = git_path[ git_path.rfind("/") + 1: ]
    #print(repo_name)
    if repo_name.find(".git") != -1 :
        repo_name = repo_name[:repo_name.find(".git")]
    return repo_name

def get_theme_repo(theme_name) :
    db = get_db()
    cur = db.execute("select theme, url from pelican_theme_table where theme = ? ", (theme_name, ))
    res = cur.fetchone()
    print(res)
    theme_url = res["url"]
    print(theme_url)
    os.chdir(APP_ROOT)
    if not os.path.exists("./theme"):
        os.mkdir("./theme")
    os.chdir("./theme")
    exitVal = subprocess.call(["git", "clone", theme_url])
    print("Clone result " + str(exitVal))
    repo_name = get_dir_from_repo(theme_url)
    os.chdir(repo_name)
    exitVal = subprocess.call(["git", "pull"])
    os.chdir(APP_ROOT)

def get_blog_repo(repo_url):
    exitVal = subprocess.call(["git", "clone", repo_url])
    os.chdir(APP_ROOT)
    if not os.path.exists("./blog"):
        os.mkdir("./blog")
    os.chdir("./blog")
    exitVal = subprocess.call(["git", "clone", repo_url])
    os.chdir(APP_ROOT)

def flash_error(val, message) :
    if val != 0 :
        flash(message, "error")

def update_blog(repo_url):
    repo_name = get_dir_from_repo(repo_url)
    os.chdir(APP_ROOT)
    blog_path = os.path.join("./blog", repo_name)
    os.chdir(blog_path)
    exitVal = subprocess.call(["git", "pull"])
    flash_error(exitVal, "Error in git pull")
    exitVal = subprocess.call(["git", "add", "."])
    flash_error(exitVal, "Error in git add ")
    exitVal = subprocess.call(["git", "commit", "-m" , "commit by thingari"])
    flash_error(exitVal, "Error in git commit")
    exitVal = subprocess.call("git", "push")
    flash_error(exitVal, "Error in git push")

def change_settings(use_git, git_repo, theme_name) :
    db = get_db()
    cur = db.execute("select * from user_table where user_name = ?", (app.config["USERNAME"],) )
    res_themes = cur.fetchall()
    print(("change settings to " + str(use_git) + str(git_repo) + str(theme_name) ))
    #print(" update theme " + str(cur.count) + str(cur.rowcount) + str(cur) + str(dir(res_themes)) + str(res_themes) )
    if len(res_themes) == 1 :
        db.execute("update user_table set theme = ?, use_git = ?, git_repo = ? where user_name = ?", (theme_name, use_git, git_repo, app.config["USERNAME"]) )
    else :
        db.execute("insert into user_table (user_name, site_generator, theme, use_git, git_repo ) values(? , ? , ? , ?, ? )" , (app.config["USERNAME"], "pelican", theme_name, use_git, git_repo) )
    db.commit()

@app.route('/admin/save_settings', methods=['POST'])
@auth.login_required
def save_settings():
    print("save_settings")
    site_generator = request.form['site_generator']
    if 'use_git' in request.form :
        use_git = True
    else:
        use_git = False
    git_repo = request.form['git_repo']
    #git_username = request.form['git_username']
    #git_password = request.form['git_password']
    theme = request.form['theme']
    change_settings(use_git, git_repo, theme)
    #print "updated table " + table.all()
    get_theme_repo(theme)
    get_blog_repo(git_repo)
    message  = '{{ "status" : "{0}", "message" : "{1}"  }}'.format("success", "")
    flash(message)
    return redirect(url_for('settings'))
    #return write_post(title, typeFile, post)

def get_theme_dir():
    db = get_db()
    cur = db.execute("select * from user_table where user_name = ?", (app.config["USERNAME"],) )
    user_res = cur.fetchone()
    user = {}
    #print(user_res)
    if user_res :
        cur = db.execute("select theme, url from pelican_theme_table where theme = ? ", (user_res["theme"], ))
        res = cur.fetchone()
        theme_url = res["url"]
        return get_dir_from_repo(theme_url)
    else :
        return None


@app.route('/admin/get_user_settings')
@auth.login_required
def get_user_settings():
    db = get_db()
    cur = db.execute("select * from user_table where user_name = ?", (app.config["USERNAME"],) )
    user_res = cur.fetchone()
    user = {}
    print(user_res)
    if user_res :
        user["theme"] = user_res["theme"]
        user["user_name"] = user_res["user_name"]
        user["git_repo"] = user_res["git_repo"]
        user["use_git"] = user_res["use_git"]
        return jsonify(user)
    else :
        return jsonify({"user" : None})

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=app.config['PORT'], debug=True)
