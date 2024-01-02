from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import aiohttp
from bs4 import BeautifulSoup


@dataclass()
class Source:
    attributes: dict[str, str]
    types: list[str]
    elements: list[str]
    components: list[str]
    all: list[str]


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
                    name = name.replace("-", "_")

                    tp = source.attributes.get(name)

                    if name in {"for", "as", "async"}:
                        name += "_"

                    attr_list.append(name)

                    if not tp:
                        tp = input(f"Type for {name}: ")
                        source.attributes[name] = tp

                        with open("attributes.json", "w") as f:
                            json.dump(source.attributes, f)

                    tp_name = f"{name.capitalize()}Type"
                    attr_src.append(
                        f"self._{name}: {tp_name} | _ImplDefinedType = {name}"
                    )

                    param_src.append(
                        f"{name}: {tp_name} | _ImplDefinedType = _ImplDefined,"
                    )
                    param_set_src.append(f"{name}={name},")
                    props.append(
                        f"""    @property
    def {name}(self) -> {tp_name} | None:
        return _handle_impl_defined(self._{name})
"""
                    )

        if ele_name == "del":
            ele_name += "_"

        source.all.append(repr(ele_name))

        src = f"""class {ele_name.capitalize()}Component(Component):
    '''
    Component class for the `<{ele_name}>` element.
    MDN Reference: {url}
    '''
    TAG_NAME: ClassVar[str] = "{ele_name}"
    ATTRIBUTE_LIST: ClassVar[list[str]] = {attr_list}

    def __init__(
        self,
        *__content: Content,
        attributes: GlobalAttributes,
        {indent(NEWLINE, 2).join(param_src)}
    ) -> None:
        super().__init__(__content, attributes)
        {indent(NEWLINE, 2).join(attr_src)}

{NEWLINE.join(props)}
        """
        source.elements.append(src)
        source.components.append(
            f"""def {ele_name}(
    *__content: Content,
    {indent(NEWLINE).join(param_src)}
    **global_attributes: Unpack[GlobalAttributes],
) -> {ele_name.capitalize()}Component:
    '''Component for the <{ele_name}> element.'''
    return {ele_name.capitalize()}Component(
        *__content,
        attributes=global_attributes,
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
    source = Source(attributes={}, types=[], elements=[], components=[], all=[])
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

    for name, tp in source.attributes.items():
        if "-" in name:
            continue

        if name in {"for", "as", "async"}:
            name += "_"

        source.types.append(f"{name.capitalize()}Type: TypeAlias = {tp}")

    print(
        "\n".join(source.types),
        "\n".join(source.elements),
        "\n".join(source.components),
        "__all__ = (" + ",".join(source.all) + ")",
        sep="\n",
        file=open("out.py", "w"),
    )


asyncio.run(main())
