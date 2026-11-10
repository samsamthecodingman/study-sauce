# Study Sauce

Exam-study skills for Claude Code. Made by Sam Roberts with Claude.

- **sauce-kb** reads your course page, the slides and worksheets on Google Drive, and forum threads, then builds your knowledge base: one notes file per week. It's built for Moodle, Ed and Panopto lecture recordings.
- **sauce-notes** turns those notes into printable exam notes: a dense two-column PDF with a chapter per week, formula boxes, hand-computation steps and checked worked examples.
- **sauce-quiz** quizzes you on those notes in Study Sauce, an interactive page with rendered maths, links back to the lecture video and slide, spaced repetition and weak-spot revision.

In Study Sauce you can also make new quizzes and practice exams, ask Claude about any question, and report a problem with one button.

[![Launch video preview: answering a quiz question in Study Sauce. Click to watch the full 97-second video](docs/launch-preview.gif)](https://cdn.jsdelivr.net/gh/samsamthecodingman/study-sauce@main/docs/study-sauce-launch.mp4)

▶️ [Watch the launch video](https://cdn.jsdelivr.net/gh/samsamthecodingman/study-sauce@main/docs/study-sauce-launch.mp4) (97 s, with sound)

![Study Sauce home: days to your next exam, weak-spot revision, and your units](docs/home.png)

| Every answer explains itself and links to the lecture moment and slide | Progress by week and concept shows what needs work |
|---|---|
| ![A quiz question with feedback and links to the lecture video and slides](docs/quiz-feedback.png) | ![Progress view with mastery per concept](docs/progress.png) |

## Install

1. Get the [Claude desktop app](https://claude.ai/download) and open the **Code** tab. (The Chat tab can't open your course site or save notes.)
2. When it asks for a folder, make a folder called `University` in your home folder and choose it.
3. Type: *"Install the study-sauce plugin from github.com/samsamthecodingman/study-sauce."* Then start a new session.
   (Or type this yourself: `/plugin install study-sauce --marketplace samsamthecodingman/study-sauce`)
4. In **Settings → Connectors**, add **Google Drive** and sign in with the Google account your course files are shared with.
5. Optional: turn on automatic updates. Type `/plugin`, go to **Marketplaces**, choose this one, and choose **Enable auto-update**.

## Updating

When a new version is out, Claude tells you at the start of a quiz session and Study Sauce shows a notice. To update, type `/plugin`, choose **study-sauce**, then **Update now**, and start a new session. (With auto-update on, this happens by itself.)

Study Sauce updates itself the next time Claude quizzes you, or ask Claude to "update my Study Sauce". Your progress stays.

Installed before 1.1.1? Update once by hand as above. Older versions can't tell you about new ones.

Had it when it was called `ma-study`? Type `/plugin`, choose **ma-study**, then **Update now**. The next time you ask Claude about studying, it switches you to **study-sauce** by itself. Your notes and Study Sauce stay.

See what changed in [Releases](https://github.com/samsamthecodingman/study-sauce/releases).

## Use

Type `/study-sauce`, or just say *"help me study for <your unit>"*. Claude opens your course site for you to sign in, asks a couple of letter-answer questions, and builds the notes. Then say *"quiz me on weeks 7–9"*.

You'll see approval prompts while it works. Read each one before approving. They should only be about reading your course site, Drive and forum, and saving notes into your `University` folder. If one asks for anything else, say no. Avoid "always allow" for commands.

Only install the plugin from this repo or a link a friend sent you. It changes what Claude does on your computer.

Course slides are sent to Claude to build your notes, and the quiz page is published to your private claude.ai Artifacts. Check your university's rules on using AI tools with course material before you share the page or the notes.

Building a whole unit uses a fair share of your Claude usage. If it stops partway, ask again and it carries on from where it stopped.

**Tip:** pin Study Sauce so it's always in your Claude sidebar. Ask Claude to "pin my Study Sauce".

## Without Claude (Codex or another agent)

You don't need Claude to use Study Sauce.

1. Get the standalone Study Sauce file from a friend who has Claude. They ask Claude to *"export my Study Sauce for sharing"*.
2. Open the file in a browser. Your progress saves in that browser, so keep using the same one.
3. To make more quizzes, use [Codex CLI](https://github.com/openai/codex) or another coding agent. Copy or symlink `skills/sauce-kb` and `skills/sauce-pack` into `~/.codex/skills`. Or just open this repo folder in the agent, and it reads `AGENTS.md`.
4. Ask it: *"make a quiz pack for <your unit> weeks 11–12"*. It needs your notes first (see sauce-kb), and it saves a `.json` file in `~/University/<your unit>/packs/`.
5. In Study Sauce, go to **Settings → Features → Quiz packs → Import** and pick that file.

## Report a problem

Use the **Report** button at the top of Study Sauce. Claude checks with you in chat before posting it as an issue here, then replies on the issue with a plan to fix it. This repo is public, so leave out personal details.
