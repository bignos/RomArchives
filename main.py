# -*- coding: utf-8 -*-

# -[ Imports ]-
import os
import re
from urllib.parse import(
    urlparse,
    unquote
)

import asyncio
import httpx
from textual import on
from textual.app import App, ComposeResult
from textual.widgets import Select, Input, DataTable, Static
from textual.containers import Vertical

from utils import (
    helpers,
    platform,
)

# -[ Constants ]-

DOWNLOAD_LIMIT = 1

# -[ Classes ]-
class Main(App):
    CSS_PATH = "tui.tcss"

    @staticmethod
    def extract_filename(url: str) -> str:
        return unquote(urlparse(url).path.split('/')[-1])

    @staticmethod
    def create_directory(directory_path: str):
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)

    async def add_to_queue(self, url : str, row, directory_path : str):
        await self.queue.put((url, row ,directory_path))
    
    async def process_queue(self):
        while not self.queue.empty():
            url, row, directory_path = await self.queue.get()
            asyncio.create_task(self.download_with_limit(
                url=url, 
                row=row, 
                directory_path=directory_path
            ))
            await asyncio.sleep(0.1)

    async def download_with_limit(self, url : str, row, directory_path: str):
        async with self.semaphore:
            await self.download_file(
                url=url, 
                row=row, 
                directory_path=directory_path
            )

    async def download_file(self, url : str, row, directory_path: str):
        async with httpx.AsyncClient(follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                total_size = int(response.headers.get("content-length", 0))
                downloaded_size = 0

                filename = Main.extract_filename(url)
                Main.create_directory(directory_path)
                full_path = os.path.join(directory_path, filename)

                with open(full_path, 'wb') as file:
                    async for chunk in response.aiter_bytes(1024):
                        downloaded_size += len(chunk)
                        file.write(chunk)
                        progress = (downloaded_size / total_size) * 100
                        progress_column = self.downloads_table.get_column("Progress")
                        cell_coord = self.downloads_table.get_cell_coordinate(row, self.download_progress_column)
                        self.downloads_table.update_cell_at(cell_coord, f"{progress:.2f}%")


    def compose(self) -> ComposeResult:
        platforms = platform.get_platforms()
        self.platform_select = Select.from_values(platforms)
        self.search_input = Input()
        self.roms_table = DataTable(name="roms_table", id="roms_table")
        self.downloads_table = DataTable(name="downloads_table", id="downloads_table")

        yield Vertical(
            Static("Platform"),
            self.platform_select,
            Static("Filter"),
            self.search_input,
            Static("Roms"),
            self.roms_table,
            Static("Downloads"),
            self.downloads_table,
        )

    def on_mount(self):
        self.queue = asyncio.Queue()
        self.semaphore = asyncio.Semaphore(DOWNLOAD_LIMIT)

        table = self.roms_table
        table.cursor_type = "row"
        table.add_column("ROM")
        table.add_column("Size")

        self.download_list = []
        downloads = self.downloads_table
        downloads.add_column("ROM")
        downloads.add_column("Size")
        self.download_progress_column = downloads.add_column("Progress")

    @on(Input.Submitted)
    def on_search_submit(self, event: Input.Changed):
        regex_query = event.value
        rom_table = self.roms_table
        rom_table.clear()

        try:
            pattern = re.compile(regex_query, re.IGNORECASE)
            self.filtered_roms = list(filter(lambda rom: pattern.search(rom['name']), self.fullset))
            for rom in self.filtered_roms:
                rom_table.add_row(rom['name'], rom['size'])
        except re.error:
            for rom in self.fullset:
                rom_table.add_row(rom['name'], rom['size'])

    @on(Select.Changed)
    def on_platform_changed(self, event: Select.Changed):
        platform_name = event.value
        if platform_name != "":
            self.fullset = platform.load_platform(platform_name)
            rom_table = self.roms_table
            rom_table.clear()
            self.search_input.value = ""
            self.filtered_roms = self.fullset
            for rom in self.filtered_roms:
                rom_table.add_row(rom['name'], rom['size'])

    @on(DataTable.RowSelected)
    async def on_rom_selected(self, event: DataTable.RowSelected):
        current_index = event.cursor_row
        rom = self.filtered_roms[current_index]

        self.download_list.append(rom)
        row = self.downloads_table.add_row( rom['name'], rom['size'], "0%")
        directory_path = next((platform["directory"] for platform in platform.CONF["platforms"] if platform["name"] == rom['platform']), None)
        await self.add_to_queue(
            url=rom['url'], 
            row=row, 
            directory_path=directory_path
        )
        await self.process_queue()
            
# -[ Private ]-

# -[ Public ]-

# -[ Main ]-

if __name__ == '__main__':
    asyncio.run(Main().run_async())
