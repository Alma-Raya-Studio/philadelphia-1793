# Contributing to Philadelphia 1793

This is a historical dataset project that synthesizes multiple primary sources. The most valuable contributions involve improving data accuracy, coverage, and linking across sources.

## Reporting Errors

If you find a discrepancy between the parsed data and an original source, please open an issue with:

1. The dataset and `entry_id` from the CSV
2. What the parsed data says
3. What the original source shows
4. The page number or location in the original

## Improving Match Rates

Cross-referencing between sources currently has limited coverage. Ways to improve this:

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
- Tax records and property assessments
- Almshouse and hospital records

## Verifying Entries

Spot-checking parsed entries against original source documents is the most valuable contribution. Even checking 10-20 entries helps.

## Code Changes

For changes to the parsing or analysis scripts:

1. Fork the repo
2. Make your changes
3. Run the full pipeline to ensure nothing breaks
4. Open a PR with a description of what changed and why

## Questions

Open an issue for questions about the data, methodology, or sources.
