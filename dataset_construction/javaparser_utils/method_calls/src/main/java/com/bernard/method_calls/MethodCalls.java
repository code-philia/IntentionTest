package com.bernard.method_calls;

import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.visitor.VoidVisitorAdapter;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.resolution.declarations.ResolvedMethodDeclaration;
import com.github.javaparser.symbolsolver.resolution.typesolvers.CombinedTypeSolver;
import com.github.javaparser.symbolsolver.JavaSymbolSolver;
import com.github.javaparser.resolution.TypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.ReflectionTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.JavaParserTypeSolver;

import java.io.File;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Set;
import java.util.Map;

/**
 * Some code that uses JavaParser.
 */
public class MethodCalls {
    static JavaSymbolSolver mainSymbolSolver = null;

    static JavaSymbolSolver alternateSymbolSolver = null;

    private static String getInternalRepresentation(ResolvedMethodDeclaration rmd) {
        String methodName = rmd.getName();
        ArrayList<String> parameters = new ArrayList<>();

        int noParams = rmd.getNumberOfParams();

        for (int i = 0; i < noParams; i++) {
            parameters.add(rmd.getParam(i).getType().describe());
            // parameters.add(rmd.getParam(i).getTypeAsString());
        }

        // String fin = "";
        // fin += methodName + "(";

        String className = rmd.getClassName();

        String fin = "";
        fin += className + "::::" + methodName + "(";
        
        for (int i = 0; i < parameters.size(); i++) {
            fin += parameters.get(i);
            if (i < parameters.size() - 1) {
                fin += ",";
            }
        }
        fin += ")";

        return fin;
    }

    private static class ClassVisitor extends VoidVisitorAdapter<Void> {
        private final Set<String> classes;

        public ClassVisitor(Set<String> classes) {
            this.classes = classes;
        }

        @Override
        public void visit(ClassOrInterfaceDeclaration n, Void arg) {
            super.visit(n, arg);

            String className = n.resolve().getClassName();

            classes.add(className);
        }
    }

    public static class MethodCallVisitor extends VoidVisitorAdapter<Void> {
        private Map<String, List<List<String>>> methodCalls = new HashMap<>();
        private Map<String, String> methodClasses = new HashMap<>();
    
        @Override
        public void visit(MethodDeclaration md, Void arg) {
            super.visit(md, arg);

            ResolvedMethodDeclaration rmdCaller = md.resolve();

            String callerMethod = getInternalRepresentation(rmdCaller); 
    
            // String methodName = md.getNameAsString();
            String mainClassName = rmdCaller.getClassName();

            methodClasses.put(callerMethod, mainClassName);

            List<List<String>> calls = new ArrayList<>();
    
            md.findAll(MethodCallExpr.class).forEach(mc -> {
                List<String> temp = new ArrayList<>();

                try {
                    // System.out.println("Method Call: " + mc.getNameAsString());
                    ResolvedMethodDeclaration rmdCallee = mc.resolve();
                    String calleeMethod = getInternalRepresentation(rmdCallee);
                    String className = rmdCallee.getClassName();

                    // Get the method name
                    // String method = mc.getNameAsString();

                    temp.add(className);
                    temp.add(calleeMethod);

                    calls.add(temp);
                } catch (Exception e) {
                    // just ignore
                }
                
            });

            methodCalls.put(callerMethod, calls);
        }
    
        public Map<String, List<List<String>>> getMethodCalls() {
            return methodCalls;
        }

        public Map<String, String> getMethodClasses() {
            return methodClasses;
        }
    }

    public static void main(String[] args) {
        String path = args[0];

        // mainJavaPath is path, where the part after /src/main/java/ is deleted
        String mainJavaPath = path.contains("/src/main/java/") 
            ? path.substring(0, path.indexOf("/src/main/java/") + 14) 
            : path.substring(0, path.indexOf("/src/test/java/") + 14);

        String alternateJavaPath = path.contains("/src/main/java/") 
            ? path.substring(0, path.indexOf("/src/main/java/")) + "/src/test/java/" 
            : path.substring(0, path.indexOf("/src/test/java/")) + "/src/main/java/";

        // Set up a combined type solver that includes reflection and JavaParser
        TypeSolver mainTypeSolver = new CombinedTypeSolver(
            new ReflectionTypeSolver(),
            new JavaParserTypeSolver(new File(mainJavaPath)) // Adjust the path accordingly
        );

        // Set up the JavaSymbolSolver with the type solver
        mainSymbolSolver = new JavaSymbolSolver(mainTypeSolver);

        // Set up a combined type solver that includes reflection and JavaParser
        TypeSolver alternateTypeSolver = new CombinedTypeSolver(
            new ReflectionTypeSolver(),
            new JavaParserTypeSolver(new File(alternateJavaPath)) // Adjust the path accordingly
        );

        // Set up the JavaSymbolSolver with the type solver
        alternateSymbolSolver = new JavaSymbolSolver(alternateTypeSolver);

        try {
            File file = new File(path);

            StaticJavaParser
                .getParserConfiguration()
                .setSymbolResolver(mainSymbolSolver);

            CompilationUnit cu = StaticJavaParser.parse(file);

            StaticJavaParser
                    .getParserConfiguration()
                    .setSymbolResolver(alternateSymbolSolver);

            CompilationUnit cu2 = StaticJavaParser.parse(file);

            Set<String> classes = new java.util.HashSet<>();

            ClassVisitor classVisitor = new ClassVisitor(classes);

            try {
                classVisitor.visit(cu, null);
            } catch (Exception e) {
                try {
                    classVisitor.visit(cu2, null);
                } catch (Exception e2) {
                    throw e2;
                }
            }

            MethodCallVisitor methodCallVisitor = new MethodCallVisitor();

            try {
                methodCallVisitor.visit(cu, null);
            } catch (Exception e) {
                try {
                    methodCallVisitor.visit(cu2, null);
                } catch (Exception e2) {
                    throw e2;
                }
            }


            Map<String, String> methodClasses = methodCallVisitor.getMethodClasses();

            // Easier parsing later on
            methodCallVisitor.getMethodCalls().forEach((method, calls) -> {
                System.out.print(method + "////");

                calls.forEach(call -> {
                    // if call.get(0) is in the classes set
                    if (call.get(0) != null && classes.contains(call.get(0))) {
                        System.out.print(call.get(1) + "----");
                    }

                    // if (call.get(0) == methodClasses.get(method)) {
                    //     System.out.print(call.get(1) + "----");
                    // }
                });

                System.out.println("");
            });
        }
        catch (Exception e) {
            // ignore
        }
        
    }
}
