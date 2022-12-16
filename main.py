#!/bin/env python
from src.config import add_config_argument, load_configs
from argparse import ArgumentParser
from importlib import import_module


def main():
    parser = ArgumentParser()
    add_config_argument(parser)

    subparser = parser.add_subparsers(
        required=True,
        dest="action",
        metavar="ACTION")

    # Actions
    # subparser.add_parser("train")
    # subparser.add_parser("test")
    subparser.add_parser("dump")

    args = parser.parse_args()
    script = import_module(f"src.scripts.{args.action}")
    config = load_configs(args.configs)
    script.main(config)
    # config = Config.load_yaml(args.config)
    # globals()[f"main_{args.action}"](config, args)


if __name__ == "__main__":
    main()
