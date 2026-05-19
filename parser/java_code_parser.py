import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tree_sitter import Language, Parser


class JavaCodeParser:
    def __init__(self):
        base_path = os.path.dirname(os.path.abspath(__file__))
        if not os.path.exists(f'{base_path}/build/my-languages.so'):
            Language.build_library(
                f'{base_path}/build/my-languages.so',  # Output shared library
                [f'{base_path}/tree-sitter-java']      # Path to the Java grammar
            )

        self.JAVA_LANGUAGE = Language(f'{base_path}/build/my-languages.so', 'java')
        self.parser = Parser()
        self.parser.set_language(self.JAVA_LANGUAGE)

        self.current_file_path = None

        # TODO add a cache to store the parsed files
        self.methods_in_file = {}
        self.constructors_in_file = {}
        
    def parse_java_file(self, file_path: str):
        with open(file_path, 'r', encoding='utf-8') as f:
            self.code = f.read()
        self.code_lines = self.code.split("\n")
        self.tree = self.parser.parse(bytes(self.code, "utf8"))
        self.current_file_path = file_path

    def parse_java_code(self, code: str):
        self.code = code
        self.code_lines = self.code.split("\n")
        self.tree = self.parser.parse(bytes(self.code, "utf8"))

    def get_implementation_given_name_line(self, target_line: int, return_range=False):
        """
        Given the line number of a method/constructor name (obtained by LSP), return its body.
        """
        candidate_constructor_name_body_pairs = self.get_all_constructor_definition()
        candidate_method_name_body_pairs = self.get_all_method_definition()
        candidate_name_body_pairs = candidate_constructor_name_body_pairs + candidate_method_name_body_pairs
        return self.select_body_from_candidates_given_name_line(candidate_name_body_pairs, target_line, return_range)

    def get_method_constructor_signature_body_given_name_line(self, target_line: int):
        """
        Given the line number of a method name (obtained by LSP), return its signature and body.
        """

        # This class omitted the explicit constructor definition
        target_line_code = self.code_lines[target_line].strip()
        if target_line_code.startswith('class ') or target_line_code.startswith('public class '):
            target_line_code_items = target_line_code.split()
            class_symbol_idx = target_line_code_items.index('class')
            class_name = target_line_code_items[class_symbol_idx + 1]
            signature = f'{class_name}()'
            return class_name, signature, '', None  # TODO: maybe refine the returned signature

        candidate_method_name_body_pairs = self.get_all_method_definition()
        candidate_constructor_name_body_pairs = self.get_all_constructor_definition()
        candidate_name_body_pairs = candidate_method_name_body_pairs + candidate_constructor_name_body_pairs

        target_pair = None
        for each_pair in candidate_name_body_pairs:
            name_node = each_pair["name"]

            if name_node.start_point[0] == target_line:
                target_pair = each_pair
                break
        if target_pair is None:
            if ' -> ' in self.code_lines[target_line]:
                print(f"This is a lambda expression at line {target_line}. Do not support lambda expression.")
            else:
                print(f"Cannot find the method/constructor name at {self.current_file_path} line {target_line}.")
            return None, None, None, None
        
        class_name, signature, body, body_end_line = self.organize_info_from_name_body_pair(target_pair)

        return class_name, signature, body, body_end_line

    def organize_info_from_name_body_pair(self, name_body_pair):
        # get signature
        name_node = name_body_pair["name"]
        details = dict([(each_node.type, each_node.text.decode("utf8")) for each_node in name_node.parent.named_children])

        signature = ''
        for each_k, each_v in details.items():
            signature += each_v + ' '
            if each_k == 'formal_parameters':
                signature = signature.strip()
                break

        # get class name from class_declaration node
        class_name = self.current_file_path.split('/')[-1].split('.')[0]

        # get body
        body_node = name_body_pair["body"]
        body = body_node.text.decode("utf8")
        body_end_line = body_node.end_point[0]

        assert len(signature) > 0 and len(body) > 0, f"The signature and body should not be empty.\nsignature:\n{signature}\n\nbody:\n{body}\n\n"

        return class_name, signature, body, body_end_line

    def get_overloaded_signatures_given_name_line(self, target_line: int):
        """
        Given the line number of a target method/constructor name (obtained by LSP), return its overloaded methods' signatures.
        """
        candidate_method_name_body_pairs = self.get_all_method_definition()
        candidate_constructor_name_body_pairs = self.get_all_constructor_definition()
        candidate_name_body_pairs = candidate_method_name_body_pairs + candidate_constructor_name_body_pairs
        return self.select_overload_given_name_line(candidate_name_body_pairs, target_line)
    
    def get_invocations_given_code_line(self, target_line: int|list):  # NOTE: the target_line starts from 0
        """
        Given the line number of a code line, return the method/constructor invocations in this line.
        return: [((line, col), method_name, arguments), ...]
        """
        candidate_invocation_line_name_arg_tuples = self.get_all_invocation()
        if isinstance(target_line, int):
            target_line = [target_line]
        return [each_tuple for each_tuple in candidate_invocation_line_name_arg_tuples if each_tuple[0][0] in target_line]

    def get_field_access_given_code_line(self, target_line: int|list):
        """
        Given the line number of a code line, return the field accesses in this line.
        """
        if isinstance(target_line, int):
            target_line = [target_line]
        candidate_field_accesses_standrad, candidate_field_accesses_other = self.get_all_field_access()  # TODO: consider the other field accesses
        field_accesses_standrad = [each_field for each_field in candidate_field_accesses_standrad if each_field[0][0] in target_line] if candidate_field_accesses_standrad else []

        return field_accesses_standrad

    def get_parameters_given_code_line(self, target_line: int|list):
        """
        Given the line number(s) of a code line(s), return the parameters in these lines.
        """
        if isinstance(target_line, int):
            target_line = [target_line]

        all_parameters = self.get_all_parameters()
        parameters_in_target_lines = [each for each in all_parameters if each[0][0] in target_line]
        return parameters_in_target_lines

    def get_all_parameters(self):
        root_node = self.tree.root_node

        # Define the query to capture parameter types and names
        query = self.JAVA_LANGUAGE.query("""
                                        (
                                        (method_declaration
                                            parameters: (formal_parameters
                                            (formal_parameter
                                                type: (_) @param_type)))
                                        )
                                        """)

        all_parameters = []
        method_param_captures = query.captures(root_node)

        query = self.JAVA_LANGUAGE.query("""
                                        (
                                        (constructor_declaration
                                            parameters: (formal_parameters
                                            (formal_parameter
                                                type: (_) @param_type)))
                                        )
                                        """)

        constructor_param_captures = query.captures(root_node)
        
        for capture in constructor_param_captures + method_param_captures:
            node = capture[0]
            all_parameters.append((node.start_point, node.text.decode('utf-8')))
        return all_parameters

    def get_all_constructor_definition(self):
        root_node = self.tree.root_node

        # Tree-sitter query to locate constructor declarations with bodies
        query = self.JAVA_LANGUAGE.query("""(constructor_declaration
                                            name: (identifier) @name
                                            body: (constructor_body) @body)""")

        # Capture query matches
        captures = query.captures(root_node)
        constructor_name_body_pairs = self.organize_definition_query_results(captures)
        return constructor_name_body_pairs

    def get_all_method_definition(self):
        """
        Get the method names and bodies in a java file.
        NOTE: this is invalid for Interface, as the method body is not defined.
        """
        root_node = self.tree.root_node

        # Tree-sitter query to locate method declarations with bodies
        query = self.JAVA_LANGUAGE.query("""
                                         (method_declaration
                                            name: (identifier) @name
                                            body: (block) @body)
                                         """)

        # Capture query matches
        captures = query.captures(root_node)
        method_name_body_pairs = self.organize_definition_query_results(captures)
        return method_name_body_pairs

    def get_all_invocation(self):
        """
        Get the method/constructor invocations in a java file.
        """
        root_node = self.tree.root_node

        # Tree-sitter query to locate method invocations
        query = self.JAVA_LANGUAGE.query("""
                                        (method_invocation
                                            name: (identifier) @name
                                            arguments: (argument_list) @args)
                                        (object_creation_expression
                                            type: (type_identifier) @name
                                            arguments: (argument_list) @args)
                                        (explicit_constructor_invocation
                                            (super) @name
                                            (argument_list) @args)
                                         """)

        # Capture query matches.
        captures = query.captures(root_node)
        assert len(captures) % 2 == 0, "The number of captures should be even."
        if captures == []:
            return []

        invocation_line_name_arg_tuples = [(captures[i][0].start_point, captures[i][0].text.decode("utf8"), captures[i+1][0].text.decode("utf8")) for i in range(0, len(captures), 2)]

        assert f'{invocation_line_name_arg_tuples[0][1][0]}' in self.code, "The invocations should be in the code."
        return invocation_line_name_arg_tuples

    def get_all_field_access(self):
        """
        Get the field accesses in a java file, such as CronFieldName.DAY_OF_MONTH
        """
        root_node = self.tree.root_node

        # Tree-sitter query to locate field accesses
        query = self.JAVA_LANGUAGE.query("""
                                         (field_access
                                         object: (identifier) @object
                                         field: (identifier) @field)
                                         """)

        # Capture query matches such as CronFieldName.DAY_OF_MONTH
        captures = query.captures(root_node)
        field_accesses_standrad = [(captures[i][0].start_point, f'{captures[i][0].text.decode("utf8")}.{captures[i+1][0].text.decode("utf8")}') for i in range(0, len(captures), 2)]

        # capture such as AlwaysFieldValueGenerator.class
        query = self.JAVA_LANGUAGE.query("(class_literal (type_identifier) @object)")
        captures = query.captures(root_node)
            # Reconstruct the class literal expression from the captured object
        field_accesses_other = [(capture[0].start_point, f"{capture[0].text.decode('utf8')}.class")
                                for capture in captures]
        return field_accesses_standrad, field_accesses_other

    def get_all_enum_definition(self):
        """
        Get all enum definitions in a java file.
        """
        root_node = self.tree.root_node

        # Tree-sitter query to locate field definitions
        query = self.JAVA_LANGUAGE.query("""
                                        (enum_declaration
                                        (enum_body
                                            (enum_constant) @constant
                                        )
                                        )
                                            """)

        enum_definitions_dict = {}
        captures = query.captures(root_node)
        for each_capture in captures:
            enum_constant_node = each_capture[0]
            enum_def = enum_constant_node.text.decode("utf8")
            enum_def_identifier = [each.text.decode("utf8") for each in enum_constant_node.parent.parent.named_children if each.type == 'identifier'][0]
            enum_def_identifier_def = enum_definitions_dict.get(enum_def_identifier, [])
            enum_def_identifier_def.append(enum_def)
            enum_definitions_dict[enum_def_identifier] = enum_def_identifier_def

        enum_definitions = []
        for each_enum_def_identifier, each_enum_def_list in enum_definitions_dict.items():
            enum_definitions.append((
                each_enum_def_identifier,
                each_enum_def_identifier,
                '{\n' + f"{', '.join(each_enum_def_list)}" + '\n}',
                self.current_file_path))

        return enum_definitions
    
    def get_all_field_definition(self):
        """
        Get all field definitions and enum definitions in a java file.
        """
        enum_definitions = self.get_all_enum_definition()
        field_definitions = self._get_all_field_definition()
        return field_definitions + enum_definitions

    def _get_all_field_definition(self):
        """
        Get all field definitions in a java file.
        """
        root_node = self.tree.root_node

        query = self.JAVA_LANGUAGE.query("""
                                        (
                                        (field_declaration
                                        ) @field_decl
                                        )
                                        """)

        captures = query.captures(root_node)

        all_field_definitions_dict = dict()
        for each_capture in captures:
            field_stat = each_capture[0].text.decode("utf8")

            parent_node = getattr(each_capture[0], 'parent')
            while 'declaration' not in parent_node.type or 'body' in parent_node.type:
                if not hasattr(parent_node, 'parent'):
                    break
                parent_node = getattr(parent_node, 'parent')

            identifier = ''
            for each_child in parent_node.named_children:
                if 'identifier' in each_child.type:
                    identifier = each_child.text.decode('utf8')
                    break
            identifier_field_def = all_field_definitions_dict.get(identifier, [])
            identifier_field_def.append(field_stat)
            all_field_definitions_dict[identifier] = identifier_field_def

        all_field_definitions = []
        for each_identifier, each_field_def_list in all_field_definitions_dict.items():
            all_field_definitions.append((
                each_identifier, 
                each_identifier, 
                '{\n' + f"\n".join(each_field_def_list) + '\n}', 
                self.current_file_path))

        return all_field_definitions
        
    def get_return_type_in_method_declaration(self, method_name_line: int):
        """
        Given the line number of a method name, return the return type and its position.
        """
        return_type_node = None
        candidate_method_name_body_pairs = self.get_all_method_definition()

        for each_pair in candidate_method_name_body_pairs:
            name_node = each_pair["name"]
            if name_node.start_point[0] == method_name_line:
                details = dict([(each_node.type, each_node) for each_node in name_node.parent.named_children])
                return_type_node = details.get('type_identifier', None)
                break
        if return_type_node is None:
            print(f'No return type found for the method at line {method_name_line}.\n{self.code}\n\n')
            return None
        
        return_type_node = (return_type_node.start_point, return_type_node.text.decode('utf8'))
        return return_type_node

    def get_method_constructor_name_in_declaration(self, method_name_line: int):
        """
        Given the line number of a method declaration, return the method name and its position.
        """
        method_name = None
        candidate_constructor_name_body_pairs = self.get_all_constructor_definition()
        candidate_method_name_body_pairs = self.get_all_method_definition()
        candidate_name_body_pairs = candidate_constructor_name_body_pairs + candidate_method_name_body_pairs

        for each_pair in candidate_name_body_pairs:
            name_node = each_pair["name"]
            if name_node.start_point[0] == method_name_line:
                method_name = (name_node.start_point, name_node.text.decode('utf8'))
                break
        if method_name is None:
            raise ValueError(f'No method name found for the method at line {method_name_line}.\n{self.code}\n\n')
        
        return method_name


    def organize_definition_query_results(self, captures):
        # Group captures by method name and method body
        methods = []
        current_method = {}

        for node, capture_name in captures:
            if capture_name == "name":
                if current_method:  # Store the previous method
                    methods.append(current_method)
                current_method = {"name": node, "body": None}
            elif capture_name == "body" and current_method:
                current_method["body"] = node

        if current_method:  # Add the last method
            methods.append(current_method)
        return methods
        
    def select_body_from_candidates_given_name_line(self, candidate_name_body_pairs: list, target_line: int, return_range=False):
        # Find the matching method declaration for the given position
        for method in candidate_name_body_pairs:
            method_name_node, method_body_node = method["name"], method["body"]
            if method_body_node is not None:  # TODO check interface
                method_start_line = method_name_node.start_point[0]  # (line, column)
                method_end_line = method_body_node.end_point[0]  # (line, column)

                # Match the position to the method's body
                if method_start_line <= target_line <= method_end_line:
                    # Extract the method body from the source code
                    method_body = self.code_lines[method_start_line: method_end_line+1]
                    if return_range:
                        return '\n'.join(method_body), method_start_line, method_end_line
                    else:
                        return '\n'.join(method_body)

        # No matching method found
        if return_range:
            return None, None, None
        else:
            return None
    
    def select_overload_given_name_line(self, candidate_name_body_pairs: list, target_line: int):
        # Find the matching method declaration for the given position
        name2signature = {}
        target_name = None
        for each_pair in candidate_name_body_pairs:
            name_node = each_pair["name"]

            if name_node.start_point[0] <= target_line <= name_node.end_point[0]:
                target_name = name_node.text.decode("utf8")
                continue

            name = name_node.text.decode("utf8")
            details = dict([(each_node.type, each_node.text.decode("utf8")) for each_node in name_node.parent.named_children])
            type_identifier = ''
            if 'type_identifier' in details:
                type_identifier = details['type_identifier']
            formal_parameters = details['formal_parameters']

            signature = f"{type_identifier} {name}{formal_parameters}"
            signatures = name2signature.get(name, [])
            signatures.append(signature)
            name2signature[name] = signatures
        overloaded_list = name2signature[target_name]
        return overloaded_list if len(overloaded_list) > 0 else None
    

if __name__ == "__main__":
    
    # field access
    java_code = """package com.cronutils.model.field;\n\npublic enum CronFieldName {\n    SECOND(0), MINUTE(1), HOUR(2), DAY_OF_MONTH(3), MONTH(4), DAY_OF_WEEK(5), YEAR(6), DAY_OF_YEAR(7);\n\n    private int order;\n    final public int testVar;\n \n    CronFieldName(final int order) {\n        this.order = order;\n    }\n\n    public int getOrder() {\n        return order;\n    }\n}\n"""

    java_code_parser = JavaCodeParser()
    java_code_parser.parse_java_code(java_code)
    field_accesses, field_accesses_other = java_code_parser.get_all_field_definition()
