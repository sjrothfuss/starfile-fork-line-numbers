from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Union, Dict, List, Generator, Optional
from importlib.metadata import version
import csv

import pandas as pd

from .utils import TextBuffer
from .typing import DataBlock

if TYPE_CHECKING:
    from os import PathLike

__version__ = version("starfile")


class StarWriter:
    def __init__(
        self,
        data_blocks: Union[DataBlock, Dict[str, DataBlock], List[DataBlock]],
        filename: Optional[PathLike] = None,
        float_format: str = '%.6f',
        separator: str = '\t',
        na_rep: str = '<NA>',
        quote_character: str = '"',
        quote_all_strings: bool = False,
    ):
        # coerce data
        self.data_blocks = self.coerce_data_blocks(data_blocks)

        if filename is not None:
            self.filename = Path(filename)
        else:
            self.filename = None
        self.float_format = float_format
        self.sep = separator
        self.na_rep = na_rep
        self.quote_character = quote_character
        self.quote_all_strings = quote_all_strings
        self.buffer = TextBuffer()
        self.backup_if_file_exists()

    def coerce_data_blocks(
        self,
        data_blocks: Union[DataBlock, List[DataBlock], Dict[str, DataBlock]]
    ) -> Dict[str, DataBlock]:
        if isinstance(data_blocks, pd.DataFrame):
            return coerce_dataframe(data_blocks)
        elif isinstance(data_blocks, dict):
            return coerce_dict(data_blocks)
        elif isinstance(data_blocks, list):
            return coerce_list(data_blocks)
        else:
            raise ValueError(
                f'Expected \
                {pd.DataFrame}, \
                {Dict[str, pd.DataFrame]} \
                or {List[pd.DataFrame]}, \
                got {type(data_blocks)}'
            )

    def lines(self) -> Generator[str, None, None]:
        yield package_info()
        yield ''
        yield ''
        for line in self.data_block_generator():
            yield line

    def write(self):
        if self.filename is None:
            raise ValueError('Cannot write nameless file!')
        with open(self.filename, mode='w+') as f:
            f.writelines(line + '\n' for line in self.lines())

    def data_block_generator(self) -> Generator[str, None, None]:
        for block_name, block in self.data_blocks.items():
            if isinstance(block, dict):
                for line in simple_block(
                    block_name=block_name,
                    data=block,
                    quote_character=self.quote_character,
                    quote_all_strings=self.quote_all_strings
                ):
                    yield line
            elif isinstance(block, pd.DataFrame):
                for line in loop_block(
                    block_name=block_name,
                    df=block,
                    float_format=self.float_format,
                    separator=self.sep,
                    na_rep=self.na_rep,
                    quote_character=self.quote_character,
                    quote_all_strings=self.quote_all_strings
                ):
                    yield line

    def backup_if_file_exists(self):
        if self.filename and self.filename.exists():
            new_name = self.filename.name + '~'
            backup_path = self.filename.resolve().parent / new_name
            if backup_path.exists():
                backup_path.unlink()
            self.filename.rename(backup_path)


def coerce_dataframe(df: pd.DataFrame) -> Dict[str, DataBlock]:
    return {'': df}


def coerce_dict(
    data_blocks: Union[DataBlock, Dict[str, DataBlock]]
) -> Dict[str, DataBlock]:
    """Coerce dict into dict of data blocks."""
    # check if data is already Dict[str, DataBlock]
    for k, v in data_blocks.items():
        if type(v) in (dict, pd.DataFrame):  #
            return data_blocks
    # coerce if not
    return {'': data_blocks}


def coerce_list(data_blocks: List[DataBlock]) -> Dict[str, DataBlock]:
    """Coerces a list of DataFrames into a dict"""
    return {f'{idx}': df for idx, df in enumerate(data_blocks)}


def package_info():
    date = datetime.now().strftime('%d/%m/%Y')
    time = datetime.now().strftime('%H:%M:%S')
    return f'# Created by the starfile Python package (version {__version__}) at {time} on {date}'


def quote(x, *,
          quote_character: str = '"',
          quote_all_strings: bool = False) -> str:
    if isinstance(x, str) and (quote_all_strings or ' ' in x or not x):
        return f'{quote_character}{x}{quote_character}'
    return x


def simple_block(
    block_name: str,
    data: Dict[str, Union[str, int, float]],
    quote_character: str = '"',
    quote_all_strings: bool = False
) -> Generator[str, None, None]:

    yield f'data_{block_name}'
    yield ''
    for k, v in data.items():
        yield f'_{k}\t\t\t{quote(v, quote_character=quote_character, quote_all_strings=quote_all_strings)}'
    yield ''
    yield ''


def loop_block(
    block_name: str,
    df: pd.DataFrame,
    float_format: str = '%.6f',
    separator: str = '\t',
    na_rep: str = '<NA>',
    quote_character: str = '"',
    quote_all_strings: bool = False,
    include_line_num: bool = True,
) -> Generator[str, None, None]:

    # Header
    yield f'data_{block_name}'
    yield ''
    yield 'loop_'
    for idx, column_name in enumerate(df.columns, 1):
        yield f'_{column_name} #{idx}' if include_line_num else f'_{column_name}'

    # Data
    for line in df.map(lambda x:
        quote(x,
              quote_character=quote_character,
              quote_all_strings=quote_all_strings)
    ).to_csv(
        mode='a',
        sep=separator,
        header=False,
        index=False,
        float_format=float_format,
        na_rep=na_rep,
        quoting=csv.QUOTE_NONE
    ).split('\n'):
        yield line

    yield ''
    yield ''
