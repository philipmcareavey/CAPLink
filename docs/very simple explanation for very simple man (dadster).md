# A Very Simple Guide (for Dadster)

Hi Dad. This is a step-by-step guide to get the CAPLink demo running on your
own computer, written for someone who has never touched a programming tool
before. Just follow the steps in order — you don't need to understand what
anything means, just do what each step says.

If something doesn't work partway through, don't panic — every step below
tells you exactly which bit of the **Troubleshooting** section (near the
bottom) to jump to for that exact problem.

At the very bottom there's also a small "what do these words mean" glossary,
in case you get curious.

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

> **Trouble here?** See Troubleshooting: ["git" or "python" isn't
> recognized](#git-or-python-isnt-recognized).

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

> **Trouble here?** See Troubleshooting: [The download/clone
> fails](#the-downloadclone-fails).

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

> **Trouble here?** See Troubleshooting: [The Python extension won't
> install](#the-python-extension-wont-install).

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

> **Trouble here?** This step has the most ways to go wrong, so check
> Troubleshooting for the one that matches what you're seeing:
> - [Nothing happens when I click the play
>   button](#nothing-happens-when-i-click-the-play-button)
> - ["No Python interpreter selected"](#no-python-interpreter-selected)
> - ["No module named uvicorn"](#no-module-named-uvicorn)
> - [The scrolling text stops with red/pink writing
>   (an error)](#the-scrolling-text-stops-with-redpink-writing)
> - [The browser never opens by
>   itself](#the-browser-never-opens-by-itself)

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

> **Trouble here?** See Troubleshooting: [I can't log
> in](#i-cant-log-in).

---

## Step 5 — How to stop it when you're done

Go back to the bottom panel where the scrolling text appeared, and look for
a red square (⏹) button near the top-right of that panel, and click it.
That switches the demo off. To start it again later, just repeat Step 3.

---

## Troubleshooting

This section is organised by problem, not by step — find the sentence
below that best matches what you're seeing. Each step above already tells
you which of these to check, so you shouldn't need to hunt around.

### "git" or "python" isn't recognized

This shows up as a red error message containing words like `'git' is not
recognized` or `'python' is not recognized`, usually right after trying
Step 1. It means one of the "Before you start" installs didn't finish
properly, or your computer hasn't noticed it yet.
- Restart your computer (this alone fixes it most of the time).
- If it still happens, reinstall the one it's complaining about (Git or
  Python) from the links in "Before you start". For Python on Windows,
  double-check you ticked **"Add python.exe to PATH"** during the install.

### The download/clone fails

If Step 1 shows an error instead of asking to open the repository:
- Make sure you're connected to the internet.
- Double-check you pasted the address exactly:
  `https://github.com/philipmcareavey/CAPLink.git`
- Try the whole of Step 1 again — a flaky internet connection is the most
  common cause.

### The Python extension won't install

- Make sure you're connected to the internet (extensions download from the
  internet, just like the initial project).
- Close VS Code fully and reopen it, then try Step 2 again.

### Nothing happens when I click the play button

Click the dropdown next to the play button (top of the "Run and Debug"
panel) and make sure **"CAPLink: Run demo (backend + browser)"** is the one
selected, not something else or nothing at all.

### "No Python interpreter selected"

Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on a Mac), type `Python: Select
Interpreter`, press Enter, and pick the option that has the word `venv`
somewhere in it. Then try Step 3 again.

### "No module named uvicorn"

This means VS Code tried to run the project using the wrong copy of
Python — one that doesn't have this project's pieces installed on it —
instead of the one Step 2 set up specifically for this project (the one
with `venv` in its name).
- Press `Ctrl+Shift+P` (or `Cmd+Shift+P`), type `Python: Select
  Interpreter`, press Enter, and choose the one that mentions `venv`.
- Then press `Ctrl+Shift+P` again, type `Developer: Reload Window`, press
  Enter (this just refreshes VS Code without closing it).
- Try Step 3 again.

### The scrolling text stops with red/pink writing

A little bit of red/pink writing appearing briefly is sometimes normal.
But if it stops completely and the browser never opens:
- Scroll up in that bottom panel and see if the very first red line
  mentions "No module named" — if so, follow the ["No module named
  uvicorn"](#no-module-named-uvicorn) fix above (same cause, whatever the
  module's name).
- Otherwise, click the red square (⏹) to stop it, then try Step 3 again —
  one retry fixes it more often than you'd think.
- Still red? Take a screenshot of the red text and send it over.

### The browser never opens by itself

Open any browser yourself and type this into the address bar (not a search
engine — the actual address bar at the very top):
```
http://localhost:8000/demo/app.html
```

### I can't log in

- Double-check you copied the email and password from the table in Step 4
  exactly, including the capital letters and the `!` at the end of the
  password.
- Make sure the bottom panel in VS Code still shows the program running
  (no red square, scrolling stopped) — if it's stopped, redo Step 3 first.

### Still stuck after all that

Close VS Code completely, open it again, and try Step 3 again. If that
still doesn't help, take a screenshot of whatever red/error text you see
(scroll up in the bottom panel if needed to catch the very first error
line) and send it over.

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
