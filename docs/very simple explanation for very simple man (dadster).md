# A Very Simple Guide (for Dadster)

Hi Dad. This is a step-by-step guide to get the CAPLink demo running on your
own computer, written for someone who has never touched a programming tool
before. Just follow the steps in order — you don't need to understand what
anything means, just do what each step says.

At the very bottom there's a small "what do these words mean" glossary, in
case you get curious.

---

## Before you start — three programs to install

You only ever have to do this once. Think of these like installing apps on
your phone — you download them, click through the installer, and you're done.

1. **Git** — a tool that lets your computer download this project.
   Download it here: https://git-scm.com/downloads
   Open the file you downloaded and click "Next" through the installer,
   leaving everything on its default setting.

2. **Python** — the programming language this project is written in.
   Download it here: https://www.python.org/downloads/
   Open the installer.
   **Important (Windows only):** on the very first screen of the installer,
   there's a checkbox near the bottom that says **"Add python.exe to PATH"**
   — tick that box before clicking Install. (Mac doesn't need this step.)

3. **VS Code** — this is the program you'll actually use to open and run the
   project. It's like a notepad that also knows how to run code.
   Download it here: https://code.visualstudio.com/download
   Open the installer and click through it with the default settings.

Once those three are installed, restart your computer once (just to be safe),
and you're ready for the next part.

---

## Step 1 — Download the project

1. Open VS Code.
2. Press `Ctrl+Shift+P` on Windows, or `Cmd+Shift+P` on a Mac. A little
   search box will pop up at the top of the window.
3. Type: `Git: Clone` and press Enter when you see it highlighted.
4. It will ask for a "repository URL" — this is just the web address of the
   project. Paste this in and press Enter:
   ```
   https://github.com/philipmcareavey/CAPLink.git
   ```
5. It will ask where to save it on your computer — pick anywhere easy to
   find, like your Desktop or Documents folder, then click "Select as
   Repository Location".
6. After a moment, a small box will pop up in the corner asking "Would you
   like to open the cloned repository?" — click **Open**.

VS Code will now reopen showing all the project's files on the left-hand
side. That means it worked.

---

## Step 2 — Let VS Code set itself up

VS Code is smart enough to notice this is a Python project and offer to set
everything up for you. Over the next few seconds, you should see one or two
small notification boxes pop up in the bottom-right corner of the window.

- If one says something like **"Install the recommended Python
  extension?"** — click **Install**.
- If one says something like **"A requirements.txt file was found... Create
  a virtual environment?"** or similar — click **Yes** / **Create** and let
  it run. This might take a minute — that's normal, it's just downloading
  everything the project needs.

**If you don't see any pop-ups at all**, don't worry, just do this instead:

1. Click the square-ish icon on the far left sidebar that looks like four
   overlapping blocks (this is the "Extensions" panel).
2. Type `python` into the search box at the top.
3. Find the one simply called **Python**, published by Microsoft, and click
   the blue **Install** button.

---

## Step 3 — Run the demo

1. On the far-left sidebar, click the icon that looks like a **play button
   with a little bug on it** (this is the "Run and Debug" panel). If you
   hover over icons and one says "Run and Debug", that's the one.
2. At the top of that panel, you should see a dropdown box. Click it and
   choose **"CAPLink: Run demo (backend + browser)"**.
3. Click the green triangle (▶) play button next to the dropdown.
4. Wait a few seconds. Some text will start scrolling in a panel at the
   bottom of the screen — that's normal, it means the program is starting
   up.
5. Your web browser should **open by itself** and show the CAPLink demo
   app. That's it — it's running!

**If the browser doesn't open by itself**, just open any browser yourself
(Chrome, Safari, Edge — whichever you normally use) and go to this address:
```
http://localhost:8000/demo/app.html
```

---

## Step 4 — Log in and have a look around

The demo already has a made-up student, a made-up business, and a made-up
university set up for you, so you can log in straight away and click
around. Use these on the demo's login screen:

| Who              | Email                            | Password       |
|------------------|-----------------------------------|-----------------|
| Student          | `aisha.rahman@manchester.ac.uk`  | `ChangeMe123!`  |
| Business         | `hello@datacraft-analytics.com`  | `ChangeMe123!`  |

Try logging in as the student first and have a look at the projects it
suggests for her.

---

## Step 5 — How to stop it when you're done

Go back to the bottom panel where the scrolling text appeared, and look for
a red square (⏹) button near the top-right of that panel, and click it.
That switches the demo off. To start it again later, just repeat Step 3.

---

## If something goes wrong

- **Nothing happens when I click the play button** — click the dropdown
  next to the play button and make sure **"CAPLink: Run demo (backend +
  browser)"** is selected, not something else.
- **It mentions "no Python interpreter selected"** — press `Ctrl+Shift+P`
  (or `Cmd+Shift+P`), type `Python: Select Interpreter`, press Enter, and
  pick the one that mentions `venv`.
- **Still stuck** — close VS Code completely, open it again, and try Step 3
  again. If that doesn't help, take a screenshot of whatever red/error text
  you see and send it over.

---

## A few words explained, in case you're curious

- **Repository ("repo")** — just a fancy word for "project folder", except
  it also remembers every change ever made to it, like a very thorough
  undo history.
- **Clone** — "download a copy of the repo onto my computer."
- **Extension** — an add-on for VS Code, like a plugin for a web browser.
- **Terminal** — a text-only window where you can type commands instead of
  clicking buttons. You didn't need to type anything in this guide, but
  you'll sometimes see one appear on screen — that's just the program
  showing you what it's doing.
- **VS Code** — the program you installed to open and run the project.
  Nothing to do with "Visual Studio" (a different, older program) despite
  the similar name.
