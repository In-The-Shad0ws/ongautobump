# Ongautobump - Companion program to Ongwatch

## The Quick

This is code from one of Twitch's moderators for the musician [Jonathan Ong](https://twitch.tv/JonathanOng) -- a stream that is both moderately complex (multiple bots, lots of hardware) and relatively long in the tooth (this year is the stream's 8th anniversary) -- which means it's picked up a decent number of different bots & codebases for making various parts of the stream work. As part of keeping the stream going, she's noticed several recurring pain points that have limited us in various ways

Its primary goal is to work with the Ongwatch bot's output to automatically log stream events into a google sheet.

See: https://github.com/alinsavix/ongwatch


## Ongautobump
Ongautobump is a utility designed to automate the administrative side of the stream by processing logs from **Ongwatch**. It monitors the raw output from the Ongwatch bot and automatically populates a Google Sheet with relevant stream data.

**Key Features:**
*   **Automated Logging:** Automatically parses and records events such as Bit donations, Tips, Subscriptions (including Gift Subs), and Raffle entries into a "Support" sheet.
*   **Hype Train Tracking:** Detects Hype Train milestones and updates the corresponding status in the spreadsheet.
*   **Song Request Management:** Processes song requests by extracting metadata (like YouTube links) and mapping them to the correct users, ensuring that even if a user provides multiple types of support, their request is correctly associated with their profile.
*   **State Persistence:** Uses a local state file to keep track of the last processed row in the Google Sheet, allowing the script to resume seamlessly after restarts or network interruptions.
*   **Robust Error Handling:** Includes automatic retries and back-off logic for Google Sheets API calls to handle potential connection issues gracefully.

See: https://github.com/alinsavix/ongwatch

