# Data sources

Datasets are not committed to this repository. This file records where every
dataset comes from so anyone can obtain the same data and reproduce the results.

Add an entry when a source is selected (roadmap stage 2) and update it whenever
data is downloaded again.

## Summary

| Source | Type | Coverage | Terms of use | Last retrieved |
| ------ | ---- | -------- | --------------- | -------------- |
| _None selected yet_ | | | | |

## Entry template

Copy this block for each source.

```markdown
### <Source name>

- **Type:** Financial prices / historical weather / weather forecasts
- **Link:** <URL>
- **Terms of use:** <Can the data be redistributed? Any usage limits?>
- **Variables used:** <e.g. adjusted close, daily max temperature>
- **Units:** <e.g. USD, °C, mm>
- **Coverage:** <assets or regions, start and end dates>
- **Frequency:** <daily, hourly, ...>
- **Time zone:** <e.g. America/New_York, UTC>
- **Availability time:** <when each value becomes known, e.g. after market close>
- **Retrieved on:** <YYYY-MM-DD>
- **Stored at:** `data/raw/<file name>`
- **Notes:** <gaps, revisions, quirks>
```
