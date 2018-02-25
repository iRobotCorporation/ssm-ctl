from __future__ import absolute_import, print_function

from textwrap import dedent

def load(s):
    return dedent(s)

class Prompter(object):
    def __init__(self, value=None, values=None):
        self.value = value
        self.values = values
        self.prompts = []
        
        self.times_prompted = 0
        
        self._index = 0
    
    def get_value(self, prompt):
        if self.value is not None:
            return self.value
        if isinstance(self.values, dict):
            value = self.values[prompt]
        else:
            value = self.values[self._index]
            self._index += 1
        return value
    
    def __call__(self, prompt):
        self.times_prompted += 1
        self.prompts.append(prompt)
        value = self.get_value(prompt)
        return value