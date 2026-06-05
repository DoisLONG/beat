# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import re
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse
debug_flag = False

class GitHubAwareRobotParser(RobotFileParser):
    """Enhanced parser specifically designed to handle GitHub's robots.txt structure with wildcard support."""

    def __init__(self, url=''):
        super().__init__(url)
        self._disallow_regexes = [] # Stores regex patterns for Disallow rules
        self._allow_regexes = [] # Stores regex patterns for Allow rules

    def parse(self, lines):
        """
            Parses the content of a robots.txt file and converts Disallow/Allow rules into regular expressions.
            Since GitHub's robots.txt may contain wildcards, this method implements custom logic
            instead of calling the parent class’s parse() method to avoid interference.
        """
        current_ua = None # Tracks the current User-agent being processed
        for line in lines:
            line = line.strip()
            # Ignore comments and empty lines
            if not line or line.startswith('#'):
                continue

            # Parse User-agent rules (can be extended for handling multiple UAs)
            if line.lower().startswith('user-agent:'):
                current_ua = line.split(':', 1)[1].strip().lower()
                # Additional logic can be implemented here to handle multiple UAs separately
            elif current_ua and (line.startswith('Disallow:') or line.startswith('Allow:')):
                field, rule = line.split(':', 1)
                rule = rule.strip()
                regex = self._convert_rule_to_regex(rule) # Convert rule into regex pattern
                if field.lower() == 'disallow':
                    self._disallow_regexes.append(regex)
                elif field.lower() == 'allow':
                    self._allow_regexes.append(regex)

        if debug_flag:
            # Optional: Print converted regex rules for debugging purposes
            print("Disallow regexes:")
            for r in self._disallow_regexes:
                print(r.pattern)
            print("Allow regexes:")
            for r in self._allow_regexes:
                print(r.pattern)

    def _convert_rule_to_regex(self, rule):
        """
            Converts robots.txt rules into regular expressions.
            Example: "/*/*/commits/" becomes "^/.*?/.*?/commits/".
        """
        if not rule:
            # An empty rule means all paths are allowed
            return re.compile(r'^$')
        # Escape special characters first, then replace wildcard '*' with '.*' for regex
        escaped = re.escape(rule)
        pattern = escaped.replace(r'\*', '.*')
        return re.compile('^' + pattern)

    def can_fetch(self, useragent, url):
        """
            Determines whether the given URL is allowed to be crawled using custom regex-based rules.
        """
        parsed = urlparse(url)
        path = parsed.path

        # If the URL matches any Allow rule, grant access
        for regex in self._allow_regexes:
            if regex.search(path):
                return True

        # If the URL matches any Disallow rule, deny access
        for regex in self._disallow_regexes:
            if regex.search(path):
                return False

        # Default to allowing access
        return True
