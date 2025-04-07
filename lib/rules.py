import re
from types import NoneType


class Rules:
    # Получение списка действий для выполняющихся правил
    def get_actions(self, item, rules):
        actions = []

        for rule_name in rules:
            if type(rules[rule_name]['conditions']) != list:
                conditions = [rules[rule_name]['conditions']]
            else:
                conditions = rules[rule_name]['conditions']

            failed = False

            for condition in conditions:
                key, operator, value = re.split(r'(<|>|<=|>=|=|!=)', condition)

                key_parts = key.split('.')

                ptr = item

                for key_part in key_parts:
                    if hasattr(ptr, key_part):
                        ptr = getattr(ptr, key_part)
                    elif type(ptr) == dict and key_part in ptr:
                        ptr = ptr[key_part]
                    else:
                        raise Exception("Failed to get property {name}".format(name=key_part))

                if not self.compare(ptr,value,operator):
                    failed = True
                    break

            if not failed:
                actions.append(rule_name)

        return actions

    # Операторы сравнения
    def compare(self, a, b, operator):
        if type(a) is NoneType and type(b) is not NoneType or type(b) is NoneType and type(a) is not NoneType: return None
        if operator == '<': return a < type(a)(b)
        if operator == '>': return a > type(a)(b)
        if operator == '=': return a == type(a)(b)
        if operator == '!=': return a != type(a)(b)
        if operator == '>=': return a >= type(a)(b)
        if operator == '<=': return a <= type(a)(b)

        return None

