# MapScraper

A Python script to automatically fetch map images and update them as needed. This is a terrible solution for getting public and private [PGM](https://github.com/PGMDev/PGM) map images together in one place.

## Setup

For the best experience, it is recommended that you set a `PA_TOKEN` (using classic Personal Access tokens) environment variable to avoid being rate limited and to access private repositories as needed.

You can also add more sources in the [`sources.json`](sources.json) file. Currently, only GitHub repositories are supported.

## Workflow

The [workflow file](.github/workflows/sync.yaml) will execute once a month to keep the Maps folder updated. It can also be executed on demand.
