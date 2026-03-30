# Contributing to Carey's Death List

This is a historical dataset project. The most valuable contributions involve improving data accuracy and coverage.

## Reporting Errors

If you find a discrepancy between the parsed data and the [original pages](https://archive.org/details/2545039R.nlm.nih.gov/page/n126/mode/1up), please open an issue with:

1. The `entry_id` from the CSV
2. What the parsed data says
3. What the original page shows
4. The page number in the original

## Improving Match Rates

The address cross-referencing currently matches ~16% of entries to the 1791 Biddle Directory. Ways to improve this:

- **Occupation synonyms**: Add mappings between equivalent historical trade names (e.g., cordwainer/shoemaker)
- **Name variants**: Add 18th-century spelling variants not currently handled
- **Fuzzy matching tuning**: Adjust thresholds or algorithms for better precision/recall
- **Additional directories**: If you have access to other Philadelphia directories from the 1790s, these could increase coverage

## Adding Data Sources

Contemporary sources that could enrich the dataset:

- Church burial records (Christ Church, St. Mary's, Gloria Dei, etc.)
- Board of Health returns
- The 1790 U.S. Census for Philadelphia
- Benjamin Rush's case notes
- Newspaper death notices from 1793

## Verifying Entries

The single most useful contribution is spot-checking entries against the original page images on the Internet Archive. Even checking 10-20 entries helps.

## Code Changes

For changes to the parsing scripts:

1. Fork the repo
2. Make your changes
3. Run the full pipeline to ensure nothing breaks
4. Open a PR with a description of what changed and why

## Questions

Open an issue for questions about the data, methodology, or sources.
