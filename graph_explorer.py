import re
from parser.java_code_parser import JavaCodeParser


class GraphExplorer:
    def __init__(self, lsp_server, max_depth, efficieny_mode: bool = False):
        self.lsp_server = lsp_server
        self.max_depth = max_depth
        self.max_usage_depth = 2
        self.max_usage_each_method = 10
        self.java_code_parser = JavaCodeParser()
        self.collected_fact_sources = set()  # the file paths where the facts are collected from.
        self.usage_position_records = set() # (path, start_line, end_line)
        self.node_source_records = dict()  # {node_type: [(start_point, name)]}
        self.fail_collect_fact_records = set()  # {fact_name}  some fact cannot be collected and the collections keep causing timeout, such as facts come from dependencies (for now) and strange invocation (in lambda project. e.g., diMapL in `Profunctor.super.<Z>diMapL(fn)`). Enable efficiency_mode for lambda project.

        self.efficieny_mode = efficieny_mode

        self.param_filter = ['T', 'Object', 'boolean', 'byte', 'char', 'short', 'int', 'long', 'float', 'double', 'String', 'Map', 'List', 'Set', 'Collection', 'Iterable', 'Iterator', 'Enumeration', 'Stream', 'Optional']

    def explore(self, file_path, target_method: str, focal_method_name: str):
        """
        explore the graph starting from the target method.
        """
        self.collected_fact_sources = set()
        self.usage_position_records = set()
        self.node_source_records = dict()

        self.focal_method_name = focal_method_name
        nodes_to_explore = self.extract_nodes_given_code_snippet(file_path, target_method)
        facts, focal_method_usages = self._explore(file_path, nodes_to_explore, 0)
        focal_method_usages = [each for each in focal_method_usages if each[2].strip() != target_method.strip()]  # remove the focal method itself.
        return facts, focal_method_usages
    
    def _explore(self, file_path, nodes_to_explore, depth):
        """
        explore the graph starting from the given nodes.
        """
        if depth == self.max_depth or len(nodes_to_explore) == 0:
            return []
        
        all_facts = []
        
        ###
        # Explore the invocation nodes.
        ###
        invoc_nodes = nodes_to_explore['invocation']
        for invoc_node in invoc_nodes:
            if self.efficieny_mode and invoc_node[1] in self.fail_collect_fact_records:
                continue

            class_name, signature, body, impl_file_path, nodes_to_explore_next_depth = self._explore_invocation_node(file_path, invoc_node)
            if signature:
                all_facts.append((class_name, signature, body, impl_file_path, depth))
                self.collected_fact_sources.add(impl_file_path)

                nodes_to_explore_next_depth = self.filter_nodes_to_explore_next(nodes_to_explore_next_depth)
                next_depth_facts = self._explore(impl_file_path, nodes_to_explore_next_depth, depth + 1)
                all_facts += next_depth_facts
                self.collected_fact_sources = self.collected_fact_sources.union(set([fact[3] for fact in next_depth_facts if len(fact) > 0]))
        
        ###
        # Explore the field access nodes.
        ###
        field_access_nodes = nodes_to_explore['field_access']
        field_definitions = []
        for field_node in field_access_nodes:
            if self.efficieny_mode and field_node[1] in self.fail_collect_fact_records:
                continue

            field_def = self._explore_field_access_node(file_path, field_node)
            if field_def:
                field_definitions += field_def
        all_facts += list(set(field_definitions))
        self.collected_fact_sources = self.collected_fact_sources.union(set([fact[3] for fact in field_definitions]))

        ###
        # Explore the parameter nodes.
        ###
        param_nodes = nodes_to_explore['parameter']
        for param_node in param_nodes:
            param_base_name = re.sub(r'[^a-zA-Z]', ' ', param_node[1]).strip()
            if len(param_base_name) == 0:
                continue

            param_base_name = param_base_name.split()[0]
            if param_base_name in self.param_filter:
                continue
            
            if self.efficieny_mode and param_node[1] in self.fail_collect_fact_records:
                continue

            all_constructors_info = self._explore_parameter_node(file_path, param_node)  # can have multiple constructors.
            for each_constructor_info in all_constructors_info:
                class_name, signature, body, impl_file_path, nodes_to_explore_next_depth = each_constructor_info
                self.collected_fact_sources.add(impl_file_path)

                all_facts.append((class_name, signature, body, impl_file_path, depth))

                nodes_to_explore_next_depth = self.filter_nodes_to_explore_next(nodes_to_explore_next_depth)
                next_depth_facts = self._explore(impl_file_path, nodes_to_explore_next_depth, depth + 1)
                all_facts += next_depth_facts
                self.collected_fact_sources = self.collected_fact_sources.union(set([fact[3] for fact in next_depth_facts]))

        ###
        # Explore the return type node. Currently only for the focal method.
        ###
        if 'return_type' in nodes_to_explore:
            return_type_node = nodes_to_explore['return_type']
            if return_type_node:
                method_definitions, field_definitions = self._explore_return_type_node(file_path, return_type_node)
                if method_definitions:
                    all_facts += list(set(method_definitions))
                    all_facts += list(set(field_definitions))

        ###
        # Recursively get the focal method's usages in the repository.
        ###
        if 'to_get_usage' in nodes_to_explore:
            usages = []
            for method_name_node in nodes_to_explore['to_get_usage']:
                message = self.lsp_server.references(file_path, {"line": method_name_node[0][0], "character": method_name_node[0][1]})

                if (len(message) == 0 
                    or 'result' not in message[0] 
                    or len(message[0]['result']) == 0):
                    continue

                for each_result in message[0]['result'][:self.max_usage_each_method]:
                    usage_file_path = each_result['uri'].replace('file://', '')
                    usage_start_line = each_result['range']['start']['line']
                    if (('/src/test/' in usage_file_path) 
                        or (usage_file_path.split('/')[-1] == file_path.split('/')[-1] and usage_start_line == method_name_node[0][0])
                        or ('Test.java' in usage_file_path)
                        or (usage_file_path.endswith('.class'))):
                        continue
                    
                    is_duplicate = False
                    for each_usage_position_record in self.usage_position_records:
                        if usage_file_path == each_usage_position_record[0] and (each_usage_position_record[1] <= usage_start_line <= each_usage_position_record[2]):
                            is_duplicate = True
                            break
                    if is_duplicate:
                        continue

                    self.java_code_parser.parse_java_file(usage_file_path)
                    method_body_contain_usage, method_body_start_line, method_body_end_line = self.java_code_parser.get_implementation_given_name_line(usage_start_line, return_range=True)
                    if not method_body_contain_usage:
                        continue
                    
                    self.usage_position_records.add((usage_file_path, method_body_start_line, method_body_end_line))

                    # when recursively exploring the usage of usage, some usages could be irrelevant to the focal method. At least the focal method name should appear in the method body.
                    method_body_contain_usage_tokens = re.findall(r'\w+', method_body_contain_usage)
                    if self.focal_method_name not in method_body_contain_usage_tokens:
                        continue

                    # get the facts in the usage
                    nodes_in_usage = self.extract_nodes_given_code_snippet_range(usage_file_path, method_body_start_line, method_body_end_line)
                    facts_in_usage = self._explore(usage_file_path, nodes_in_usage, self.max_depth - 1)  # just get the impl or definitions of these nodes, not further explore.
                    usages.append((usage_file_path, usage_start_line, method_body_contain_usage, facts_in_usage))

                    # recursively consider the usage of the usage.
                    # consider its usages (so extract its name node).
                    if depth < self.max_usage_depth:
                        self.java_code_parser.parse_java_file(usage_file_path)
                        method_name_node_recursive = self.java_code_parser.get_method_constructor_name_in_declaration(method_body_start_line)
                        nodes_to_explore_next_depth = {'invocation': [], 'parameter': [], 'field_access': []}
                        nodes_to_explore_next_depth['to_get_usage'] = [method_name_node_recursive]
                        _, usage_recursive = self._explore(usage_file_path, nodes_to_explore_next_depth, depth + 1)
                        usages += usage_recursive

            # all_facts += list(set(usages))
        if 'to_get_usage' in nodes_to_explore:
            return list(set(all_facts)), usages
        else:
            return list(set(all_facts))

    def _explore_invocation_node(self, file_path, invoc_node):
        """
        Get invocation nodes' implementation and signature, and extract the nodels within the implementation which will be further explored.
        """
        invoc_start_line, invoc_start_column = invoc_node[0]
        if invoc_node[1] == 'super':
            message = self.lsp_server.definition(file_path, {"line": invoc_start_line, "character": invoc_start_column})
        else:
            message = self.lsp_server.implementation(file_path, {"line": invoc_start_line, "character": invoc_start_column})

        impl_file_path, impl_start_line = self.extract_file_path_start_line_from_lsp_msg(message)
        if impl_file_path is None:
            self.fail_collect_fact_records.add(invoc_node[1])
            return None, None, None, None, None
        
        # Get the signature and body of the implementation.
        self.java_code_parser.parse_java_file(impl_file_path)
        class_name, signature, body, impl_end_line = self.java_code_parser.get_method_constructor_signature_body_given_name_line(impl_start_line)

        # Extract nodes from the implementation.
        nodes_to_explore = dict()
        if body:
            nodes_to_explore = self.extract_nodes_given_code_snippet_range(impl_file_path, impl_start_line, impl_end_line)

        return class_name, signature, body, impl_file_path, nodes_to_explore
    
    def _explore_field_access_node(self, file_path, field_node):
        """
        Get the field definitions in the file where the field access node' definition is.
        """
        # get the field access node definition.
        message = self.lsp_server.type_definition(file_path, {"line": field_node[0][0], "character": field_node[0][1]})
        def_file_path, def_start_line = self.extract_file_path_start_line_from_lsp_msg(message)
        if def_file_path is None:
            self.fail_collect_fact_records.add(field_node[1])
            return None
        
        # get all the public field definitions in the def_file
        self.java_code_parser.parse_java_file(def_file_path)
        field_definitions = self.java_code_parser.get_all_field_definition()
        return field_definitions

    def _explore_parameter_node(self, file_path, param_node):
        """
        Get the contructor definition and implementation of the parameter node, and extract the nodes within the implementation which will be further explored.
        """
        param_node_line, param_node_column = param_node[0]
        param_node_name = param_node[1]
        if '.' in param_node_name:
            param_node_column = param_node_column + len(param_node_name)
        
        # cannot directly reuse the _explore_invocation_node method, as it jumps to the class definition, not the constructor definition. So here just get the file path where the constructor is defined.
        message = self.lsp_server.implementation(file_path, {"line": param_node_line, "character": param_node_column})
        impl_file_path, _ = self.extract_file_path_start_line_from_lsp_msg(message)
        if impl_file_path is None:
            self.fail_collect_fact_records.add(param_node[1])
            return []
        
        # Get all constructors' definition and implementation.
        all_constructors_info = []
        self.java_code_parser.parse_java_file(impl_file_path)
        constructor_name_body_pairs = self.java_code_parser.get_all_constructor_definition()
        for each_pair in constructor_name_body_pairs:
            impl_start_line = each_pair['name'].start_point[0]
            class_name, signature, body, impl_end_line = self.java_code_parser.get_method_constructor_signature_body_given_name_line(impl_start_line)
            if signature is None:
                continue

            # Extract nodes from the implementation.
            nodes_to_explore = dict()
            if body:
                nodes_to_explore = self.extract_nodes_given_code_snippet_range(impl_file_path, impl_start_line, impl_end_line)
            all_constructors_info.append((class_name, signature, body, impl_file_path, nodes_to_explore))
        
        return all_constructors_info

    def _explore_return_type_node(self, file_path, return_type_node):
        """
        Get the return type node's info, i.e., the definitions of methods and fields in the class.
        """
        return_type_node_line, return_type_node_column = return_type_node[0]
        message = self.lsp_server.implementation(file_path, {"line": return_type_node_line, "character": return_type_node_column})
        impl_file_path, impl_start_line = self.extract_file_path_start_line_from_lsp_msg(message)
        if impl_file_path is None:
            self.fail_collect_fact_records.add(return_type_node[1])
            return None, None
        
        self.java_code_parser.parse_java_file(impl_file_path)
        field_definitions = self.java_code_parser.get_all_field_definition()

        method_definitions = []
        method_name_body_pairs = self.java_code_parser.get_all_method_definition()
        for each_name_body_pair in method_name_body_pairs:
            class_name, signature, body, body_end_line = self.java_code_parser.organize_info_from_name_body_pair(each_name_body_pair)
            method_definitions.append((class_name, signature, body, impl_file_path, body_end_line))

        return method_definitions, field_definitions

    def extract_file_path_start_line_from_lsp_msg(self, message):
        """
        check if the LSP message is valid.
        """
        if len(message) == 0:
            return None, None

        if 'result' not in message[0]:
            return None, None

        results = message[0]['result']
        if len(results) == 0:
            return None, None
        
        choice_idx = 0
        if len(results) > 1:
            for each_idx, each_result in enumerate(results):
                file_path = each_result['uri'].replace('file://', '')
                if file_path in self.collected_fact_sources:
                    choice_idx = each_idx
                    break
        
        try:
            file_path = results[choice_idx]['uri'].replace('file://', '')
            start_line = results[choice_idx]['range']['start']['line']
        except Exception as e:
            print(f"[ERROR]\n{results} \n\n")
            return None, None

        # TODO: support parse .class file in the jar.
        if ('.class' in file_path
            or '/src/test/' in file_path):  
            return None, None
        
        return file_path, start_line

    def filter_nodes_to_explore_next(self, nodes_to_explore):
        """
        filter the nodes that have been explored according to the node_source_records.
        """
        resulting_nodes_to_explore = dict()
        for node_type in nodes_to_explore:
            filtered_nodes = []
            record = self.node_source_records.get(node_type, [])

            for each_node in nodes_to_explore[node_type]:
                start_point, name = each_node[0], each_node[1]
                if (start_point, name) in record:
                    continue
                
                if self.efficieny_mode:
                    if node_type == 'invocation' and each_node[1] in self.fail_collect_fact_records:
                        continue
                    elif node_type == 'parameter' and each_node[1] in self.fail_collect_fact_records:
                        continue
                    elif node_type == 'field_access' and each_node[1] in self.fail_collect_fact_records:
                        continue

                filtered_nodes.append(each_node)
                record.append((start_point, name))
            resulting_nodes_to_explore[node_type] = filtered_nodes
            self.node_source_records[node_type] = record
        return resulting_nodes_to_explore

    def extract_nodes_given_code_snippet(self, file_path: str, code_snippet: str):
        ###
        # get code_snippet position in the file.
        ###
        with open(file_path, 'r') as f:
            java_code = f.read()
        
        java_code_lines = java_code.split('\n')
        code_snippet_lines = code_snippet.strip().split('\n')
        while code_snippet_lines[0].strip().startswith('@'):
            code_snippet_lines = code_snippet_lines[1:]

        candidate_line_idxs = [i for i, line in enumerate(java_code_lines) if line.strip() == code_snippet_lines[0].strip()]
        if len(candidate_line_idxs) == 0:
            raise Exception(f"Failed to find the code snippet in the file\nFile Path: {file_path}\nCode Snippet: {code_snippet}\n\n")
        elif len(candidate_line_idxs) > 1:
            for n_tries in range(1, len(code_snippet_lines)):  # see the following lines to find the correct code snippet.
                filter_candidate_line_idxs = []
                for each in candidate_line_idxs:
                    if java_code_lines[each + n_tries].strip() != code_snippet_lines[0 + n_tries].strip():
                        continue
                    filter_candidate_line_idxs.append(each)
                if len(filter_candidate_line_idxs) == 1:
                    method_start_line = filter_candidate_line_idxs[0]
                    break
                candidate_line_idxs = filter_candidate_line_idxs
            if len(filter_candidate_line_idxs) != 1:
                raise Exception(f"Found multiple code snippets in the file\nFile Path: {file_path}\nCode Snippet: {code_snippet}\n\n")
        else:
            method_start_line = candidate_line_idxs[0]
        
        while '(' not in java_code_lines[method_start_line]:
            method_start_line += 1

        method_start_line, method_end_line = self.get_method_constructor_body_range_given_start_line(file_path, method_start_line)
        if method_end_line is None:
            raise Exception(f"Failed to get the method body range\nFile Path: {file_path}\nCode Snippet: {code_snippet}\n\n")

        nodes = self.extract_nodes_given_code_snippet_range(file_path, method_start_line, method_end_line)

        ###
        # for the focal method
        ###
        # consider its return type
        self.java_code_parser.parse_java_file(file_path)
        return_type_node = self.java_code_parser.get_return_type_in_method_declaration(method_start_line)

        nodes['return_type'] = return_type_node if return_type_node else None  # if focal method is a constructor, return_type_node is None.

        # consider its usages (so extract its name node).
        method_name_node = self.java_code_parser.get_method_constructor_name_in_declaration(method_start_line)
        nodes['to_get_usage'] = [method_name_node]

        # If focal method is not a constructor, consider its constructor
        constructor_definitions = self.java_code_parser.get_all_constructor_definition()
        if method_name_node[1] not in [each['name'].text.decode('utf8') for each in constructor_definitions]:
            for each in constructor_definitions:
                # the nodes within the constructor should be collected.
                nodes_in_focal_constructor = self.extract_nodes_given_code_snippet_range(file_path, each['name'].start_point[0], each['body'].end_point[0])

                for each_node_in_focal_cons in nodes_in_focal_constructor:
                    nodes[each_node_in_focal_cons] += nodes_in_focal_constructor[each_node_in_focal_cons]
                # the constructor's usage should be considered
                nodes['to_get_usage'].append((each['name'].start_point, each['name'].text.decode('utf8')))

                # TODO: the parameter's usage should be considered.
        return nodes

    def get_method_constructor_body_range_given_start_line(self, file_path, start_line):
        self.java_code_parser.parse_java_file(file_path)
        class_name, signature, body, body_end_line = self.java_code_parser.get_method_constructor_signature_body_given_name_line(start_line)

        return start_line, body_end_line
    
    def extract_nodes_given_code_snippet_range(self, file_path: str, start_line: int, end_line: int):
        """
        extract nodes from the given code snippet range, including: parameters, method invocations, constructor invocations, and field accesses.
        Each node is represented as a tuple with first item is a tuple (start_point_line, start_point_column).
        """
        self.java_code_parser.parse_java_file(file_path)

        invocation_nodes = self.java_code_parser.get_invocations_given_code_line(list(range(start_line, end_line + 1)))

        parameter_nodes = self.java_code_parser.get_parameters_given_code_line(list(range(start_line, end_line + 1)))

        field_access_nodes = self.java_code_parser.get_field_access_given_code_line(list(range(start_line, end_line + 1)))
        
        nodes = {
            'invocation': invocation_nodes,
            'parameter': parameter_nodes,
            'field_access': field_access_nodes
            }

        return nodes