<div align="center"><img src="https://raw.githubusercontent.com/ZeroIntensity/view.py/master/html/logo.png" alt="view.py logo" width=250 height=auto /></div>

<div align="center"><h2>The Batteries-Detachable Web Framework</h2></div>

> [!Warning]
> view.py is currently in alpha, and may be lacking some features.
> If you would like to follow development progress, be sure to join [the discord](https://discord.gg/tZAfuWAbm2).

<div align="center">
    <a href="https://clientarea.space-hosting.net/aff.php?aff=303"><img width=150 height=auto src="https://cdn-dennd.nitrocdn.com/fygsTSpFNuiCdXWNTtgOTVMRlPWNnIZx/assets/images/optimized/rev-758b0f8/www.space-hosting.net/wp-content/uploads/2023/02/cropped-Icon.png"></a>
    <h3>view.py is affiliated with <a href="https://clientarea.space-hosting.net/aff.php?aff=303">Space Hosting</a></h3>
</div>

-   [Docs](https://view.zintensity.dev)
-   [Source](https://github.com/ZeroIntensity/view.py)
-   [PyPI](https://pypi.org/project/view.py)
-   [Discord](https://discord.gg/tZAfuWAbm2)

## Features

-   Batteries Detachable: Don't like our approach to something? No problem! We aim to provide native support for all your favorite libraries, as well as provide APIs to let you reinvent the wheel as you wish.
-   Lightning Fast: Powered by [pyawaitable](https://github.com/ZeroIntensity/pyawaitable), view.py is the first web framework to implement ASGI in pure C, without the use of external transpilers.
-   Developer Oriented: view.py is developed with ease of use in mind, providing a rich documentation, docstrings, and type hints.

See [why I wrote it](https://view.zintensity.dev/#why-did-i-build-it) on the docs.

## Examples

```py
from view import new_app

app = new_app()

@app.get("/")
async def index():
    return await app.template("index.html", engine="jinja")

app.run()
```

```py
# routes/index.py
from view import get, HTML

# Build TypeScript Frontend
@get(steps=["typescript"], cache_rate=1000)
async def index():
    return await HTML.from_file("dist/index.html")
```

```py
from view import JSON, body, post

@post("/create")
@body("name", str)
@body("books", dict[str, str])
def create(name: str, books: dict[str, str]):
    # ...
    return JSON({"message": "Successfully created user!"}), 201
```

## Installation

**Python 3.8+ is required.**

### Development

```console
$ pip install git+https://github.com/ZeroIntensity/view.py
```

### PyPI

```console
$ pip install view.py
```

### Pipx

```console
$ pipx install view.py
```
