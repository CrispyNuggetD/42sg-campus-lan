import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from campus_lan.cohort_display import cohort_index


class CohortDisplay(unittest.TestCase):
    def test_local_cache_is_minimized_and_conflicting_duplicates_are_unknown(self):
        with tempfile.TemporaryDirectory() as tmp,patch('campus_lan.cohort_display.directory',return_value=Path(tmp)):
            path=Path(tmp)/'singapore.json'
            path.write_text(json.dumps({'students':[
                {'login':'fixture4','cohort':4,'private_field':'NOT FOR DISPLAY'},
                {'login':'fixture5','cohort':5},
                {'login':'ambiguous','cohort':4},{'login':'ambiguous','cohort':5},
                {'login':'invalid','cohort':True},{'login':'unknown','cohort':None}]}))
            self.assertEqual(cohort_index(),{'fixture4':4,'fixture5':5})

    def test_missing_or_invalid_cache_does_not_guess_or_fetch(self):
        with tempfile.TemporaryDirectory() as tmp,patch('campus_lan.cohort_display.directory',return_value=Path(tmp)):
            self.assertEqual(cohort_index(),{})
            (Path(tmp)/'singapore.json').write_text('{broken')
            self.assertEqual(cohort_index(),{})
