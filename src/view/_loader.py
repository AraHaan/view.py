from __future__ import annotations

import os
import runpy
import warnings
from typing import TYPE_CHECKING

from ._logging import Internal
from .routing import Method, Route, RouteInput
from .typing import RouteInputDict

if TYPE_CHECKING:
    from .app import ViewApp


def _format_inputs(inputs: list[RouteInput]) -> list[RouteInputDict]:
    result: list[RouteInputDict] = []

    for i in inputs:
        if i.tp:
            if i.tp not in {str, int, bool, float}:
                if i.tp is not dict:
                    if not hasattr(i.tp, "__view_body__"):
                        raise TypeError(
                            f"{i.tp.__name__} is not a valid body type",
                        )

        result.append(
            {
                "name": i.name,
                "type": i.tp,
                "default": i.default,
                "validators": i.validators,
                "is_body": i.is_body,
            }
        )

    return result


def finalize(routes: list[Route], app: ViewApp):
    targets = {
        Method.GET: app._get,
        Method.PATCH: app._post,
        Method.PUT: app._put,
        Method.PATCH: app._patch,
        Method.DELETE: app._delete,
        Method.OPTIONS: app._options,
    }

    for route in routes:
        target = targets[route.method]

        if not route.path:
            raise TypeError("route did not specify a path")

        target(
            route.path,
            route.callable,
            route.cache_rate,
            _format_inputs(route.inputs),
        )


def load_fs(app: ViewApp, target_dir: str):
    Internal.info("loading using filesystem")
    Internal.debug(f"loading {app}")

    routes: list[Route] = []

    for root, _, files in os.walk(target_dir):
        for f in files:
            if f.startswith("_"):
                continue

            path = os.path.join(root, f)
            Internal.info(f"loading: {path}")
            mod = runpy.run_path(path)
            route: Route | None = None

            for i in mod.values():
                if isinstance(i, Route):
                    if route:
                        warnings.warn("set route twice!")
                    route = i

            if not route:
                raise ValueError(f"{path} has no set route")

            if route.path:
                warnings.warn(
                    "path was passed when filesystem loading is enabled"
                )
            else:
                route.path = path.rsplit(".", maxsplit=1)[0]

            routes.append(route)

    finalize(routes, app)


def load_simple(app: ViewApp, target_dir: str):
    Internal.info("loading using simple strategy")
    routes: list[Route] = []

    for root, _, files in os.walk(target_dir):
        for f in files:
            if f.startswith("_"):
                continue

            path = os.path.join(root, f)
            Internal.info(f"loading: {path}")
            mod = runpy.run_path(path)
            mini_routes: list[Route] = []

            for i in mod.values():
                if isinstance(i, Route):
                    mini_routes.append(i)

            for route in mini_routes:
                if not route.path:
                    raise ValueError(
                        "omitting path is only supported"
                        " on filesystem loading",
                    )

                routes.append(route)

    finalize(routes, app)
