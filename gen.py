from __future__ import annotations

import asyncio
from typing import Any, NamedTuple

import aiohttp
from bs4 import BeautifulSoup


class Source(NamedTuple):
    attributes: dict[str, str]
    types: list[str]
    elements: list[str]
    components: list[str]


async def _add_elements(
    url: str,
    source: Source,
    session: aiohttp.ClientSession,
    name: str,
) -> None:
    print(f"Downloading {name}...")
    attr_src: list[str] = []

    async with session.get(url) as res:
        text = await res.text()
        soup = BeautifulSoup(text)
        attrs = soup.find(id="attributes")
        assert attrs
        parent = attrs.parent
        assert parent
        div = parent.find("div")
        assert div
        dl = div.find("dl")
        assert dl

        print(f"Handling attributes for {url}")
        for i in dl.find_all("dt"):  # type: ignore
            print(i.get("id"))

    src = f"""class {name.capitalize()}(Element):
    TAG_NAME: ClassVar[str] = "{name}"
    ATTRIBUTE_LIST: ClassVar[list[str]] = [{attr_list}]

    def __init__(self, *content: Content, attributes: GlobalAttributes) -> None:
        super().__init__(content, attributes)
        {attr_src}
    """
    source.elements.append(src)


async def _search_elements(
    element: Any, source: Source, session: aiohttp.ClientSession
):
    tasks = []
    for i in element.children:
        a = i.find("a")
        if not i.find("abbr"):
            code = a.find("code")
            text = code.get_text().replace("<", "").replace(">", "")
            tasks.append(
                _add_elements(
                    "https://developer.mozilla.org" + a.get("href"),
                    source,
                    session,
                    text,
                )
            )

    await asyncio.gather(*tasks)


async def main():
    source = Source(attributes={}, types=[], elements=[], components=[])
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://developer.mozilla.org/en-US/docs/Web/HTML/Element"
        ) as res:
            text = await res.text()
            soup = BeautifulSoup(text, features="html.parser")
            for summary in soup.find_all("summary"):
                if summary.get_text() == "HTML elements":
                    await _search_elements(
                        summary.parent.find("ol"), source, session
                    )


asyncio.run(main())
