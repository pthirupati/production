"""Seed the public Tutorials section with original written content.

ALL prose and code examples below are original content authored for FixitLab.
Nothing is copied or paraphrased from any third-party tutorial site. Re-running
the command is idempotent: it updates the tutorial in place and replaces its
sections, so editing the content here and re-seeding keeps the DB in sync.

Usage:
    python manage.py seed_tutorials
    python manage.py seed_tutorials --flush   # delete tutorials first
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.tutorials.models import Tutorial, TutorialSection


# Each tutorial is a dict; ``sections`` is a list of (heading, body, code,
# code_language, code_caption) tuples. Original content only.
TUTORIALS: list[dict] = [
    # ─────────────────────────────────────────────────────────────────────────
    {
        "slug": "linux-command-line-basics",
        "title": "Linux Command Line Basics",
        "summary": "Move around the filesystem, read and edit files, and manage permissions from the shell.",
        "topic": "Linux",
        "difficulty": "beginner",
        "estimated_minutes": 12,
        "order": 10,
        "playground_slug": "linux",
        "scenario_slug": "",
        "seo_title": "Linux Command Line Basics — A Beginner's Hands-On Guide",
        "seo_description": "Learn the essential Linux shell commands for navigation, files, and permissions, then try them live in a free in-browser terminal.",
        "seo_keywords": "linux, command line, terminal, bash, chmod, ls, cd, beginner",
        "sections": [
            (
                "Why the shell is worth learning",
                "Graphical file managers are convenient, but the command line is where Linux really lives. "
                "Almost every server you will ever touch is administered through a shell, and once a task needs "
                "to be repeated or automated, typed commands beat clicking every time.\n\n"
                "A shell is simply a program that reads what you type, runs it, and prints the result. The most "
                "common one is Bash. When you see a prompt ending in a dollar sign, the shell is waiting for a command.",
                "",
                "",
                "",
            ),
            (
                "Finding out where you are",
                "Every shell session has a 'current directory' — the folder your commands act on by default. "
                "Three commands answer the questions you will ask constantly: who am I, where am I, and what is here?",
                "whoami        # the user you are logged in as\n"
                "pwd           # print working directory (where you are)\n"
                "ls            # list the files in the current directory\n"
                "ls -la        # long listing, including hidden dotfiles",
                "bash",
                "Run these one at a time and read each result before moving on.",
            ),
            (
                "Moving around with cd",
                "The `cd` (change directory) command moves you between folders. A path that starts with `/` is "
                "absolute (measured from the root of the filesystem); anything else is relative to where you are now. "
                "Two shortcuts save a lot of typing: `~` means your home directory, and `..` means the parent folder.",
                "cd /etc        # jump to an absolute path\n"
                "cd ..          # go up one level\n"
                "cd ~           # back to your home directory\n"
                "cd             # with no argument, also goes home",
                "bash",
                "",
            ),
            (
                "Reading files without opening an editor",
                "You rarely need a full editor just to glance at a file. `cat` dumps a whole file, while `head` and "
                "`tail` show only the first or last lines — invaluable for large log files where you only care about "
                "the newest entries.",
                "cat /etc/os-release        # show the whole file\n"
                "head -n 5 /etc/passwd      # first 5 lines\n"
                "tail -n 20 /var/log/messages   # last 20 log lines",
                "bash",
                "",
            ),
            (
                "Understanding file permissions",
                "In a long listing the first column looks like `-rw-r--r--`. Read it in groups of three: the owner's "
                "permissions, the group's, then everyone else's. `r` is read, `w` is write, and `x` is execute. "
                "The `chmod` command changes these bits. The numeric form treats each group as a digit (read=4, "
                "write=2, execute=1), so `chmod 644 file` means owner read+write, everyone else read-only.",
                "ls -l notes.txt            # inspect current permissions\n"
                "chmod 600 secret.txt       # only the owner can read/write\n"
                "chmod +x deploy.sh         # make a script executable",
                "bash",
                "644 = rw-r--r--, 600 = rw-------, 755 = rwxr-xr-x.",
            ),
            (
                "Where to go next",
                "You now have the core loop: see where you are, move, look at files, and adjust permissions. The fastest "
                "way to make these stick is to type them yourself. Open the free Linux terminal playground and work "
                "through the commands above — there is nothing to install and nothing to break.",
                "",
                "",
                "",
            ),
        ],
    },
    # ─────────────────────────────────────────────────────────────────────────
    {
        "slug": "bash-scripting-introduction",
        "title": "Introduction to Bash Scripting",
        "summary": "Turn repetitive commands into reusable scripts with variables, conditionals, and loops.",
        "topic": "Bash",
        "difficulty": "beginner",
        "estimated_minutes": 14,
        "order": 20,
        "playground_slug": "bash",
        "scenario_slug": "",
        "seo_title": "Introduction to Bash Scripting — Variables, Loops, and Conditionals",
        "seo_description": "Write your first Bash scripts: variables, if-statements, for-loops, and exit codes. Practise live in a free shell sandbox.",
        "seo_keywords": "bash, shell script, scripting, variables, loops, conditionals, automation",
        "sections": [
            (
                "From commands to scripts",
                "A Bash script is just a text file containing the same commands you would type at the prompt, run "
                "from top to bottom. The first line, called the shebang, tells the system which interpreter to use. "
                "Saving a sequence of commands once and running it on demand is the foundation of automation.",
                "#!/usr/bin/env bash\n"
                "echo \"Starting the backup run\"\n"
                "echo \"Done\"",
                "bash",
                "Save as backup.sh, then make it runnable with: chmod +x backup.sh",
            ),
            (
                "Variables hold values",
                "Assign a variable with no spaces around the equals sign, and read it back by prefixing the name with "
                "a dollar sign. Wrapping the expansion in double quotes is a habit worth forming early: it keeps values "
                "with spaces from being split into separate words.",
                "name=\"web-01\"\n"
                "count=3\n"
                "echo \"Restarting ${name} (${count} times)\"",
                "bash",
                "Output: Restarting web-01 (3 times)",
            ),
            (
                "Making decisions with if",
                "Conditionals let a script react to its environment. The test brackets `[[ ... ]]` evaluate a "
                "condition; common checks are `-f` (a file exists), `-z` (a string is empty), and `-eq` (numbers are "
                "equal). Indentation is optional but makes the structure obvious.",
                "if [[ -f /etc/nginx/nginx.conf ]]; then\n"
                "  echo \"nginx config is present\"\n"
                "else\n"
                "  echo \"nginx config is missing\"\n"
                "fi",
                "bash",
                "",
            ),
            (
                "Repeating work with loops",
                "A `for` loop walks over a list of items, binding each one to a variable in turn. This is the natural "
                "way to apply the same action to several hosts, files, or numbers without copying and pasting.",
                "for host in web-01 web-02 db-01; do\n"
                "  echo \"Checking ${host}...\"\n"
                "done\n\n"
                "for i in $(seq 1 3); do\n"
                "  echo \"attempt ${i}\"\n"
                "done",
                "bash",
                "",
            ),
            (
                "Exit codes signal success or failure",
                "Every command returns an exit code: zero means success, anything else means failure. The special "
                "variable `$?` holds the most recent code. Scripts and CI pipelines rely on this convention to decide "
                "whether to keep going or stop, so it is worth exiting with a meaningful code yourself.",
                "ls /tmp > /dev/null\n"
                "echo \"ls exit code: $?\"\n\n"
                "if ! ping -c1 example.com > /dev/null 2>&1; then\n"
                "  echo \"host unreachable\" >&2\n"
                "  exit 1\n"
                "fi",
                "bash",
                "Redirecting to >&2 sends the message to standard error.",
            ),
            (
                "Try it yourself",
                "The best way to learn scripting is to run small snippets and watch what they do. Paste the loops and "
                "conditionals above into the Bash playground, change the values, and see how the output reacts.",
                "",
                "",
                "",
            ),
        ],
    },
    # ─────────────────────────────────────────────────────────────────────────
    {
        "slug": "git-version-control-essentials",
        "title": "Git Version Control Essentials",
        "summary": "Track changes, commit history, and work with branches the way real teams do.",
        "topic": "Git",
        "difficulty": "beginner",
        "estimated_minutes": 13,
        "order": 30,
        "playground_slug": "git",
        "scenario_slug": "",
        "seo_title": "Git Version Control Essentials — Commits, Branches, and Merging",
        "seo_description": "Understand the Git workflow: staging, committing, branching, and merging. Practise the commands in a free Git sandbox.",
        "seo_keywords": "git, version control, commit, branch, merge, staging area, workflow",
        "sections": [
            (
                "What Git actually tracks",
                "Git records snapshots of your project over time so you can see what changed, when, and by whom — and "
                "roll back if something breaks. Unlike simply copying folders, Git stores the full history compactly and "
                "lets many people work on the same code without overwriting each other.\n\n"
                "A Git project lives in a repository. You create one with a single command, and from then on Git watches "
                "the folder for changes.",
                "git init               # start tracking the current folder\n"
                "git status             # see what has changed",
                "bash",
                "",
            ),
            (
                "The three states of a change",
                "This is the idea that unlocks Git. A modified file starts as 'unstaged'. You move it to the 'staging "
                "area' with `git add`, choosing exactly what will go into the next snapshot. Then `git commit` records "
                "the staged changes as a permanent point in history with a message describing them.",
                "git add app.py            # stage one file\n"
                "git add .                 # stage everything changed\n"
                "git commit -m \"Add health-check endpoint\"",
                "bash",
                "Write commit messages in the imperative: 'Add', 'Fix', 'Remove'.",
            ),
            (
                "Reading the history",
                "Once you have a few commits, the log is your project's story. The one-line format is the everyday view; "
                "each commit has a unique hash you can use to refer back to it.",
                "git log --oneline\n"
                "git log --oneline --graph    # show branch structure too",
                "bash",
                "Example: a1b2c3d Add health-check endpoint",
            ),
            (
                "Branching for parallel work",
                "A branch is an independent line of development. Creating one lets you build a feature or try a risky "
                "change without disturbing the main branch. Most teams keep `main` always-deployable and do their work "
                "on short-lived feature branches.",
                "git branch feature-login      # create a branch\n"
                "git checkout feature-login    # switch to it\n"
                "git checkout -b feature-login # create AND switch in one step",
                "bash",
                "",
            ),
            (
                "Merging your work back",
                "When a feature is ready, you bring its commits back into the main branch with a merge. Switch to the "
                "branch you want to merge into first, then merge the feature branch. If the same lines changed in both "
                "places, Git reports a conflict and asks you to resolve it.",
                "git checkout main\n"
                "git merge feature-login\n"
                "git branch -d feature-login   # delete the merged branch",
                "bash",
                "",
            ),
            (
                "Practise the workflow",
                "Git rewards muscle memory. Open the Git practice sandbox and run a full cycle: init a repo, make a "
                "commit, branch off, commit again, and merge back. Doing it once makes the model click.",
                "",
                "",
                "",
            ),
        ],
    },
    # ─────────────────────────────────────────────────────────────────────────
    {
        "slug": "docker-getting-started",
        "title": "Getting Started with Docker",
        "summary": "Understand images and containers, and run your first containerised workloads.",
        "topic": "Docker",
        "difficulty": "beginner",
        "estimated_minutes": 15,
        "order": 40,
        "playground_slug": "docker",
        "scenario_slug": "",
        "seo_title": "Getting Started with Docker — Images, Containers, and the CLI",
        "seo_description": "Learn the difference between Docker images and containers and the everyday docker commands. Try them in a free Docker playground.",
        "seo_keywords": "docker, containers, images, dockerfile, docker run, devops, containerisation",
        "sections": [
            (
                "Images versus containers",
                "These two words trip up almost everyone at first, so let's be precise. An image is a read-only template "
                "— a packaged filesystem plus the metadata needed to run a program. A container is a running instance of "
                "an image. The relationship mirrors a program on disk versus a process in memory: one image can spawn "
                "many containers, and stopping a container does not delete the image.",
                "docker images          # list images you have locally\n"
                "docker ps              # list running containers\n"
                "docker ps -a           # include stopped containers",
                "bash",
                "",
            ),
            (
                "Running your first container",
                "`docker run` takes an image name and starts a container from it. If the image is not present locally, "
                "Docker downloads it first. The `-d` flag runs the container in the background (detached), and `-p` "
                "publishes a container port to your host so you can reach the service.",
                "docker run hello-world\n"
                "docker run -d -p 8080:80 --name web nginx\n"
                "# the nginx site is now reachable on localhost:8080",
                "bash",
                "",
            ),
            (
                "Inspecting and controlling containers",
                "Once something is running you will want to see its logs, look inside it, and stop it cleanly. `docker "
                "logs` streams a container's output, and `docker exec` runs a command inside an already-running "
                "container — most often an interactive shell for debugging.",
                "docker logs web                 # view the container's output\n"
                "docker exec -it web sh          # open a shell inside it\n"
                "docker stop web && docker rm web   # stop, then remove",
                "bash",
                "The -it flags give you an interactive terminal.",
            ),
            (
                "Describing an image with a Dockerfile",
                "To package your own application you write a Dockerfile: a recipe of instructions Docker follows to "
                "build an image. Each instruction adds a layer. A typical file starts from a base image, copies your "
                "code in, installs dependencies, and declares the command to run.",
                "FROM python:3.12-slim\n"
                "WORKDIR /app\n"
                "COPY requirements.txt .\n"
                "RUN pip install --no-cache-dir -r requirements.txt\n"
                "COPY . .\n"
                "CMD [\"python\", \"app.py\"]",
                "dockerfile",
                "Build it with: docker build -t myapp:1.0 .",
            ),
            (
                "Why containers matter",
                "Because an image bundles the application together with its dependencies, it runs the same way on your "
                "laptop, in CI, and in production. That consistency — 'it works on my machine' becomes 'it works "
                "everywhere' — is the reason containers reshaped how software is shipped.",
                "",
                "",
                "",
            ),
            (
                "Try the commands live",
                "Open the Docker playground and run the lifecycle yourself: list images, start a container, read its "
                "logs, exec into it, and tear it down. Seeing the state change after each command builds real intuition.",
                "",
                "",
                "",
            ),
        ],
    },
    # ─────────────────────────────────────────────────────────────────────────
    {
        "slug": "kubernetes-core-concepts",
        "title": "Kubernetes Core Concepts",
        "summary": "Pods, Deployments, and Services explained — and the kubectl commands to see them.",
        "topic": "Kubernetes",
        "difficulty": "intermediate",
        "estimated_minutes": 16,
        "order": 50,
        "playground_slug": "kubernetes",
        "scenario_slug": "",
        "seo_title": "Kubernetes Core Concepts — Pods, Deployments, and Services",
        "seo_description": "Understand the building blocks of Kubernetes and the essential kubectl commands. Explore a simulated cluster in a free playground.",
        "seo_keywords": "kubernetes, k8s, pods, deployments, services, kubectl, orchestration",
        "sections": [
            (
                "What Kubernetes is for",
                "Running one container is easy; running hundreds across many machines, keeping them healthy, and routing "
                "traffic to them is not. Kubernetes is a container orchestrator: you describe the state you want — say, "
                "'three copies of this app should always be running' — and it continuously works to make reality match "
                "that description, restarting and rescheduling containers as needed.",
                "kubectl get nodes           # the machines in your cluster\n"
                "kubectl cluster-info        # where the control plane lives",
                "bash",
                "",
            ),
            (
                "Pods: the smallest unit",
                "Kubernetes does not schedule containers directly — it schedules Pods. A Pod wraps one (occasionally a "
                "few tightly-coupled) containers that share a network address and storage. You rarely create Pods by "
                "hand, but you list and inspect them constantly when debugging.",
                "kubectl get pods\n"
                "kubectl get pods -A             # across all namespaces\n"
                "kubectl describe pod <name>     # detailed status and events",
                "bash",
                "",
            ),
            (
                "Deployments keep Pods running",
                "A Deployment is the object you usually create. It declares how many replicas of a Pod you want and which "
                "image they run. If a Pod crashes or a node dies, the Deployment's controller creates a replacement so "
                "the replica count is maintained. Rolling out a new image is just an update to the Deployment.",
                "apiVersion: apps/v1\n"
                "kind: Deployment\n"
                "metadata:\n"
                "  name: web\n"
                "spec:\n"
                "  replicas: 3\n"
                "  selector:\n"
                "    matchLabels:\n"
                "      app: web\n"
                "  template:\n"
                "    metadata:\n"
                "      labels:\n"
                "        app: web\n"
                "    spec:\n"
                "      containers:\n"
                "        - name: web\n"
                "          image: nginx:1.27",
                "yaml",
                "Apply with: kubectl apply -f deployment.yaml",
            ),
            (
                "Services give Pods a stable address",
                "Pods come and go, and each gets a different IP, so you never talk to a Pod directly from another app. A "
                "Service provides a single, stable name and address that load-balances across all the Pods matching a "
                "label. This decouples callers from the churn of individual Pods.",
                "kubectl get services\n"
                "kubectl expose deployment web --port=80 --type=ClusterIP",
                "bash",
                "",
            ),
            (
                "The declarative mindset",
                "The thread tying all of this together is that you declare desired state and Kubernetes reconciles it. You "
                "do not write scripts that say 'start a container here'; you write manifests that say 'this should "
                "exist', and the system makes it so — and keeps it so. Internalising that shift is most of the battle.",
                "",
                "",
                "",
            ),
            (
                "Explore a live cluster",
                "Open the Kubernetes playground to run kubectl against a simulated cluster. List the nodes, inspect Pods "
                "and Deployments, and watch how the objects relate to one another.",
                "",
                "",
                "",
            ),
        ],
    },
    # ─────────────────────────────────────────────────────────────────────────
    {
        "slug": "python-fundamentals-for-beginners",
        "title": "Python Fundamentals for Beginners",
        "summary": "Variables, data types, control flow, and functions — the foundations of Python.",
        "topic": "Python",
        "difficulty": "beginner",
        "estimated_minutes": 15,
        "order": 60,
        "playground_slug": "python",
        "scenario_slug": "",
        "seo_title": "Python Fundamentals for Beginners — Variables, Loops, and Functions",
        "seo_description": "Start programming in Python: variables, lists, conditionals, loops, and functions, with runnable examples in a free online compiler.",
        "seo_keywords": "python, programming, beginner, variables, functions, loops, lists, tutorial",
        "sections": [
            (
                "Your first Python program",
                "Python is prized for reading almost like English, which makes it a forgiving first language. A program is "
                "just a sequence of statements run top to bottom. The `print` function writes to the screen and is the "
                "tool you will reach for most while learning, to see what your code is doing.",
                "print(\"Hello, FixitLab!\")\n"
                "print(\"Python runs line by line.\")",
                "python",
                "",
            ),
            (
                "Variables and basic types",
                "A variable is a name bound to a value; you create one simply by assigning to it. Python figures out the "
                "type for you. The everyday types are integers and floats for numbers, strings for text, and booleans "
                "for true/false. You can check any value's type with the built-in `type` function.",
                "name = \"Ada\"          # a string\n"
                "age = 36               # an integer\n"
                "height = 1.7           # a float\n"
                "is_engineer = True     # a boolean\n"
                "print(name, age, height, is_engineer)",
                "python",
                "",
            ),
            (
                "Lists hold many values",
                "When you need a collection of items in order, use a list. Lists are written with square brackets, are "
                "indexed from zero, and can grow or shrink. They are the workhorse container in Python.",
                "servers = [\"web-01\", \"web-02\", \"db-01\"]\n"
                "print(servers[0])         # first item -> web-01\n"
                "servers.append(\"cache-01\")  # add to the end\n"
                "print(len(servers))       # how many items -> 4",
                "python",
                "",
            ),
            (
                "Making decisions and repeating work",
                "Control flow decides which statements run. An `if`/`elif`/`else` chain branches on conditions, while a "
                "`for` loop repeats a block once per item in a collection. Python uses indentation — not braces — to mark "
                "which lines belong to a block, so consistent spacing is part of the syntax, not just style.",
                "for server in servers:\n"
                "    if server.startswith(\"db\"):\n"
                "        print(server, \"is a database\")\n"
                "    else:\n"
                "        print(server, \"is a web/cache node\")",
                "python",
                "",
            ),
            (
                "Functions package reusable logic",
                "A function gives a name to a block of code so you can call it repeatedly with different inputs. Define "
                "one with `def`, list its parameters in parentheses, and hand back a result with `return`. Functions are "
                "how you keep programs organised as they grow.",
                "def greet(person, times=1):\n"
                "    for _ in range(times):\n"
                "        print(f\"Hello, {person}!\")\n\n"
                "greet(\"Grace\")\n"
                "greet(\"Linus\", times=2)",
                "python",
                "The f before the string lets you embed variables in braces.",
            ),
            (
                "Run it in the browser",
                "Reading Python only gets you so far. Open the Python compiler playground, paste these snippets, and "
                "experiment — change the values, break things on purpose, and read the errors. That feedback loop is the "
                "fastest way to learn.",
                "",
                "",
                "",
            ),
        ],
    },
    # ─────────────────────────────────────────────────────────────────────────
    {
        "slug": "postgresql-sql-basics",
        "title": "SQL Basics with PostgreSQL",
        "summary": "Query and modify relational data with SELECT, WHERE, JOIN, and aggregates.",
        "topic": "PostgreSQL",
        "difficulty": "beginner",
        "estimated_minutes": 16,
        "order": 70,
        "playground_slug": "sql",
        "scenario_slug": "",
        "seo_title": "SQL Basics with PostgreSQL — SELECT, WHERE, JOIN, and GROUP BY",
        "seo_description": "Learn to query relational databases with SQL: filtering, sorting, joining tables, and aggregating. Run every example in a free SQL console.",
        "seo_keywords": "sql, postgresql, database, select, join, where, group by, query",
        "sections": [
            (
                "Tables, rows, and columns",
                "A relational database stores data in tables, which are simply grids: each row is one record and each "
                "column is one attribute. SQL is the language you use to ask questions of that data and to change it. "
                "Everything that follows works against an `employees` table with columns for name, role, and hire date.",
                "-- the shape we are querying\n"
                "-- employees(id, name, role, hired)",
                "sql",
                "",
            ),
            (
                "Selecting and filtering rows",
                "The `SELECT` statement reads data. List the columns you want (or `*` for all of them) and the table to "
                "read from. A `WHERE` clause keeps only the rows matching a condition, which is how you avoid pulling "
                "back an entire table when you want a slice of it.",
                "SELECT name, role FROM employees;\n\n"
                "SELECT name FROM employees\n"
                "WHERE role = 'sre';",
                "sql",
                "Text values go in single quotes.",
            ),
            (
                "Sorting and limiting results",
                "`ORDER BY` arranges the output by one or more columns, ascending by default or descending with `DESC`. "
                "`LIMIT` caps how many rows come back — handy for 'top N' style questions and for peeking at a large "
                "table without overwhelming yourself.",
                "SELECT name, hired FROM employees\n"
                "ORDER BY hired DESC\n"
                "LIMIT 3;",
                "sql",
                "This returns the three most recently hired people.",
            ),
            (
                "Aggregating with GROUP BY",
                "Often you want a summary rather than individual rows: how many, the average, the maximum. Aggregate "
                "functions like `count`, `avg`, and `max` collapse many rows into one value. `GROUP BY` runs the "
                "aggregate once per group, so you can ask 'how many people are in each role?' in a single query.",
                "SELECT role, count(*) AS headcount\n"
                "FROM employees\n"
                "GROUP BY role\n"
                "ORDER BY headcount DESC;",
                "sql",
                "AS gives the computed column a readable name.",
            ),
            (
                "Combining tables with JOIN",
                "The real power of relational databases is relating tables to each other. If an `incidents` table records "
                "which employee each incident is assigned to, a `JOIN` stitches the two together on the matching id so "
                "you can show the person's name next to the incident — instead of an opaque numeric reference.",
                "SELECT i.title, e.name AS assignee\n"
                "FROM incidents AS i\n"
                "JOIN employees AS e ON e.id = i.assignee_id\n"
                "WHERE i.resolved = 0;",
                "sql",
                "",
            ),
            (
                "Changing data",
                "Reading is only half the story. `INSERT` adds rows, `UPDATE` modifies existing ones, and `DELETE` "
                "removes them. Always pair `UPDATE` and `DELETE` with a `WHERE` clause — without one they affect every "
                "row in the table, which is a classic and costly mistake.",
                "INSERT INTO employees (name, role) VALUES ('Dana', 'sre');\n\n"
                "UPDATE incidents SET resolved = 1 WHERE id = 2;\n\n"
                "DELETE FROM incidents WHERE resolved = 1;",
                "sql",
                "",
            ),
            (
                "Practise on real data",
                "The SQL console playground starts with the exact `employees` and `incidents` tables used above, already "
                "populated. Run each query, then try writing your own — change the filters, add a JOIN, or insert a row "
                "and query it back.",
                "",
                "",
                "",
            ),
        ],
    },
    # ─────────────────────────────────────────────────────────────────────────
    {
        "slug": "ansible-automation-introduction",
        "title": "Introduction to Ansible Automation",
        "summary": "Describe server configuration as code with inventories, playbooks, and idempotent tasks.",
        "topic": "Ansible",
        "difficulty": "intermediate",
        "estimated_minutes": 15,
        "order": 80,
        "playground_slug": "ansible",
        "scenario_slug": "",
        "seo_title": "Introduction to Ansible Automation — Playbooks and Inventories",
        "seo_description": "Learn how Ansible automates server configuration with inventories, playbooks, modules, and idempotent tasks. Try the commands in a free playground.",
        "seo_keywords": "ansible, automation, playbook, inventory, idempotent, configuration management, devops",
        "sections": [
            (
                "Configuration as code, without agents",
                "Ansible automates the setup and maintenance of servers. Instead of logging into each machine and running "
                "commands by hand, you write down the desired configuration once and apply it to many hosts at once. Its "
                "defining trait is that it is agentless: it connects over plain SSH, so there is no software to install "
                "on the machines you manage.",
                "ansible --version\n"
                "ansible localhost -m ping     # check connectivity to a host",
                "bash",
                "The ping module confirms Ansible can reach and run on a host.",
            ),
            (
                "The inventory lists your hosts",
                "Ansible needs to know which machines to manage; that list is the inventory. You can group hosts so a "
                "play can target, say, all webservers at once. A simple inventory is just an INI-style file of "
                "group headers and hostnames.",
                "[webservers]\n"
                "web-01.example.com\n"
                "web-02.example.com\n\n"
                "[databases]\n"
                "db-01.example.com",
                "ini",
                "Save as inventory.ini and pass it with -i inventory.ini.",
            ),
            (
                "Modules do the actual work",
                "A module is a small, focused unit of work — install a package, copy a file, start a service. You can run "
                "a single module directly from the command line for one-off tasks, which is great for quick checks "
                "before you commit logic to a playbook.",
                "# install nginx on every webserver, ad-hoc\n"
                "ansible webservers -m ansible.builtin.package \\\n"
                "  -a \"name=nginx state=present\" --become",
                "bash",
                "--become runs the task with elevated (sudo) privileges.",
            ),
            (
                "Playbooks describe the desired state",
                "A playbook is a YAML file that ties hosts to an ordered list of tasks, each invoking a module. This is "
                "where Ansible shines: the playbook reads as documentation of exactly how a host should be configured, "
                "and it is version-controlled like any other code.",
                "- name: Configure web servers\n"
                "  hosts: webservers\n"
                "  become: true\n"
                "  tasks:\n"
                "    - name: Ensure nginx is installed\n"
                "      ansible.builtin.package:\n"
                "        name: nginx\n"
                "        state: present\n\n"
                "    - name: Ensure nginx is running\n"
                "      ansible.builtin.service:\n"
                "        name: nginx\n"
                "        state: started\n"
                "        enabled: true",
                "yaml",
                "Run it with: ansible-playbook -i inventory.ini site.yml",
            ),
            (
                "Idempotence is the key idea",
                "Notice the tasks above say 'ensure', not 'install' or 'start'. Ansible modules are idempotent: they "
                "describe a target state and only act if reality differs from it. Running the same playbook twice is "
                "safe — the second run reports 'ok' for tasks already in the desired state and changes nothing. This is "
                "what makes Ansible safe to run repeatedly and on schedule.",
                "",
                "",
                "",
            ),
            (
                "Try the commands",
                "Open the Ansible playground to run the version, ping, and help commands hands-on and get comfortable "
                "with the tooling before you write a full playbook of your own.",
                "",
                "",
                "",
            ),
        ],
    },
]


class Command(BaseCommand):
    help = "Seed the public Tutorials section with original written content (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete all existing tutorials before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            deleted, _ = Tutorial.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Flushed existing tutorials ({deleted} rows)."))

        created = 0
        updated = 0
        # Built-in tutorials plus any original tutorials authored as data in
        # data/tutorials_extra.json (sections may be 5-item lists or tuples).
        specs = [dict(s) for s in TUTORIALS]
        import json
        import os
        extra_path = os.path.join(os.path.dirname(__file__), "data", "tutorials_extra.json")
        e3_path = os.path.join(os.path.dirname(__file__), "data", "tutorials_e3_batch.json")
        e3b_path = os.path.join(os.path.dirname(__file__), "data", "tutorials_e3_batch2.json")
        e3c_path = os.path.join(os.path.dirname(__file__), "data", "tutorials_e3_batch3.json")
        e3d_path = os.path.join(os.path.dirname(__file__), "data", "tutorials_e3_batch4.json")
        if os.path.exists(extra_path):
            try:
                with open(extra_path, encoding="utf-8") as fh:
                    extra = json.load(fh)
                if isinstance(extra, list):
                    specs.extend(extra)
                    self.stdout.write(f"  + loaded {len(extra)} tutorials from tutorials_extra.json")
            except Exception as exc:
                self.stderr.write(f"  ! could not load tutorials_extra.json: {exc}")
        if os.path.exists(e3_path):
            try:
                with open(e3_path, encoding="utf-8") as fh:
                    e3 = json.load(fh)
                if isinstance(e3, list):
                    specs.extend(e3)
                    self.stdout.write(f"  + loaded {len(e3)} tutorials from tutorials_e3_batch.json")
            except Exception as exc:
                self.stderr.write(f"  ! could not load tutorials_e3_batch.json: {exc}")
        if os.path.exists(e3b_path):
            try:
                with open(e3b_path, encoding="utf-8") as fh:
                    e3b = json.load(fh)
                if isinstance(e3b, list):
                    specs.extend(e3b)
                    self.stdout.write(f"  + loaded {len(e3b)} tutorials from tutorials_e3_batch2.json")
            except Exception as exc:
                self.stderr.write(f"  ! could not load tutorials_e3_batch2.json: {exc}")
        if os.path.exists(e3c_path):
            try:
                with open(e3c_path, encoding="utf-8") as fh:
                    e3c = json.load(fh)
                if isinstance(e3c, list):
                    specs.extend(e3c)
                    self.stdout.write(f"  + loaded {len(e3c)} tutorials from tutorials_e3_batch3.json")
            except Exception as exc:
                self.stderr.write(f"  ! could not load tutorials_e3_batch3.json: {exc}")
        if os.path.exists(e3d_path):
            try:
                with open(e3d_path, encoding="utf-8") as fh:
                    e3d = json.load(fh)
                if isinstance(e3d, list):
                    specs.extend(e3d)
                    self.stdout.write(f"  + loaded {len(e3d)} tutorials from tutorials_e3_batch4.json")
            except Exception as exc:
                self.stderr.write(f"  ! could not load tutorials_e3_batch4.json: {exc}")
        for spec in specs:
            sections = spec.pop("sections", [])
            obj, was_created = Tutorial.objects.update_or_create(
                slug=spec["slug"],
                defaults=spec,
            )
            # Replace sections wholesale so editing content here re-syncs cleanly.
            obj.sections.all().delete()
            TutorialSection.objects.bulk_create(
                [
                    TutorialSection(
                        tutorial=obj,
                        order=i,
                        heading=heading,
                        body=body,
                        code=code,
                        code_language=code_language or "bash",
                        code_caption=code_caption,
                    )
                    for i, (heading, body, code, code_language, code_caption) in enumerate(sections)
                ]
            )
            # Restore sections key for idempotent re-runs within one process.
            spec["sections"] = sections
            if was_created:
                created += 1
            else:
                updated += 1

        total_sections = TutorialSection.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded tutorials: {created} created, {updated} updated, "
                f"{total_sections} sections total."
            )
        )
