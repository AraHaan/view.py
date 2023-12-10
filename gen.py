from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any

import aiohttp
from bs4 import BeautifulSoup, Tag


@dataclass()
class Source:
    attributes: dict[str, str]
    types: list[str]
    elements: list[str]
    components: list[str]


PATTERN = re.compile(r"(?<!^)(?=[A-Z])")


def to_snake(name: str) -> str:
    return PATTERN.sub("_", name).lower()


NEWLINE: str = "\n"


def indent(line: str, amount: int = 1) -> str:
    return line + ("    " * amount)


async def _add_elements(
    url: str,
    source: Source,
    session: aiohttp.ClientSession,
    ele_name: str,
) -> None:
    try:
        print(f"Downloading {ele_name}...")
        attr_src: list[str] = []
        attr_list = []
        param_src = []
        param_set_src = []
        props = []

        async with session.get(url) as res:
            text = await res.text()
            soup = BeautifulSoup(text, features="html.parser")
            attrs = soup.find(id="attributes")
            assert attrs
            parent = attrs.parent
            assert parent
            div = parent.find("div")
            assert div
            dl = div.find("dl")
            if dl:
                print(f"Handling attributes for {url}")
                for i in dl.find_all("dt"):  # type: ignore
                    if i.parent != dl:
                        continue

                    if i.find("abbr"):
                        continue

                    name = i.get("id")
                    attr_list.append(name)
                    tp = source.attributes.get(name)
                    if not tp:
                        tp = input(f"Type for {name}: ")
                        source.attributes[name] = tp

                        with open("attributes.json", "w") as f:
                            json.dump(source.attributes, f)

                    tp_name = f"{name.capitalize()}Type"
                    source.types.append(f"{tp_name} = {tp}")
                    if "present" not in tp.lower():
                        attr_src.append(f"self.{name}: {tp_name} = {name}")
                    else:
                        attr_src.append(
                            f"self.{name}: {tp_name} = {name} if {name} is not True else ''"
                        )

                    param_src.append(f"{name}: {tp_name} | None = None,")
                    param_set_src.append(f"{name}={name}")

            for th in soup.find_all("th", scope="row"):
                if th.get_text() == "DOM interface":
                    tr = th.parent
                    td = tr.find("td")
                    assert td
                    interface = td.find("a")
                    assert interface
                    async with session.get(
                        "https://developer.mozilla.org" + interface.get("href"),
                    ) as interface_res:
                        interface_soup = BeautifulSoup(
                            await interface_res.text(), features="html.parser"
                        )
                        dl = interface_soup.find("dl")
                        for index, dt in enumerate(dl.children):  # type: ignore
                            if not isinstance(dt, Tag):
                                continue

                            if dt.name != "dt":
                                continue

                            if dt.find("abbr"):
                                continue

                            id = dt.get("id")
                            assert isinstance(id, str)
                            id = id.split(".", maxsplit=1)[-1]
                            dd = list(dl.children)[index + 2]  # type: ignore
                            desc = dd.find("p").get_text()  # type: ignore

                            props.append(
                                f"""@property
    def {to_snake(id)}(self):
        '''{desc}'''
        return self._element().{id}
"""
                            )

        src = f"""class {ele_name.capitalize()}(Element):
    '''
    Element class for the `<{ele_name}>` element.
    MDN Reference: {url}
    '''
    TAG_NAME: ClassVar[str] = "{ele_name}"
    ATTRIBUTE_LIST: ClassVar[list[str]] = {attr_list}

    def __init__(
        self,
        *content: Content,
        attributes: GlobalAttributes,
        {indent(NEWLINE, 2).join(param_src)}
    ) -> None:
        super().__init__(content, attributes)
        {indent(NEWLINE, 2).join(attr_src)}

    {NEWLINE.join(props)}
        """
        source.elements.append(src)
        source.components.append(
            f"""def {ele_name}(
    *content: Content,
    {indent(NEWLINE).join(param_src)}
    **global_attributes: GlobalAttributes,
) -> {ele_name.capitalize()}:
    '''Component for the <{ele_name}> element.'''
    return {ele_name.capitalize()}(
        *content,
        global_attributes,
        {indent(NEWLINE, 2).join(param_set_src)}
    )"""
        )
    except KeyboardInterrupt:
        print(
            "\n".join(source.types),
            "\n".join(source.elements),
            "\n".join(source.components),
            sep="\n",
        )
        exit()


async def _search_elements(
    element: Any, source: Source, session: aiohttp.ClientSession
):
    for i in element.children:
        a = i.find("a")
        if not i.find("abbr"):
            code = a.find("code")
            text = code.get_text().replace("<", "").replace(">", "")
            await _add_elements(
                "https://developer.mozilla.org" + a.get("href"),
                source,
                session,
                text,
            )


async def main():
    source = Source(attributes={}, types=[], elements=[], components=[])
    with open("attributes.json") as f:
        source.attributes = json.load(f)
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
