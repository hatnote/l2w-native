# Listen to Wikipedia Native

Non-browser-based Listen to Wikipedia application, based on Kivy.

## Commands

Python for Android build commands.

Distribution build:

```./distribute.sh -m "kivy twisted autobahn"```

Build:

```
 time ./build.py --package org.hatnote.l2w --name "Listen to Wikipedia" --permission INTERNET --version 0.1 --orientation=portrait --dir ~/hatnote/l2w_app/l2w_app debug installd
```

(Will probably switch this to Buildozer)
