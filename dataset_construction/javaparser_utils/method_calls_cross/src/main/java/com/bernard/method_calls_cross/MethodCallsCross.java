package com.bernard.method_calls_cross;

import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.visitor.VoidVisitorAdapter;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.expr.MethodCallExpr;

import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
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
import java.util.Map;
import java.util.Set;

/**
 * Some code that uses JavaParser.
 */
public class MethodCallsCross {
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

    public static class MethodCallVisitor extends VoidVisitorAdapter<Void> {
        private Map<String, List<List<String>>> methodCalls = new HashMap<>();
        private Map<String, String> methodClasses = new HashMap<>();
    
        @Override
        public void visit(MethodDeclaration md, Void arg) {
            super.visit(md, arg);

            ResolvedMethodDeclaration rmdCaller = md.resolve();

            String callerMethod = getInternalRepresentation(rmdCaller); 
    
            // String methodName = md.getNameAsString();
            String mainClassName = md.resolve().getClassName();
            
            // get the types of the parameters
            // md.getParameters().forEach(p -> {
            //     System.out.println("Parameter: " + p.getNameAsString() + ", Type: " + p.getTypeAsString());
            // });

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

    public static void main(String[] args) {
        String path = args[0];

        // mainJavaPath is path, where the part after /src/main/java/ is deleted
        String mainJavaPath = path.substring(0, path.indexOf("/src/test/java/")) + 
            "/src/main/java/";
        
        String temp = path.substring(path.lastIndexOf("/") + 1, path.lastIndexOf("."));
        // remove the Test from className
        temp = temp.substring(0, temp.length() - 4);

        final String className = temp;

        System.out.println("Classname: " + className);

        // Set up a combined type solver that includes reflection and JavaParser
        TypeSolver typeSolver = new CombinedTypeSolver(
            new ReflectionTypeSolver(),
            new JavaParserTypeSolver(new File(mainJavaPath)) // Adjust the path accordingly
        );

        // Set up the JavaSymbolSolver with the type solver
        JavaSymbolSolver symbolSolver = new JavaSymbolSolver(typeSolver);

        try {
            File file = new File(path);

            StaticJavaParser
                .getParserConfiguration()
                .setSymbolResolver(symbolSolver);

            CompilationUnit cu = StaticJavaParser.parse(file);

            // System.out.println(path.replace("Test", "").replace("test", "main"));

            CompilationUnit cu_main = StaticJavaParser.parse(new File(path.replace("Test", "")
                .replace("src/test/java", "src/main/java")));

            Set<String> classes = new java.util.HashSet<>();

            ClassVisitor classVisitor = new ClassVisitor(classes);

            classVisitor.visit(cu_main, null);

            MethodCallVisitor methodCallVisitor = new MethodCallVisitor();

            methodCallVisitor.visit(cu, null);

            Map<String, String> methodClasses = methodCallVisitor.getMethodClasses();

            // Easier parsing later on
            methodCallVisitor.getMethodCalls().forEach((method, calls) -> {
                System.out.print(method + "////");

                calls.forEach(call -> {
                    // if (call.get(0).equals(className)) {
                    //     System.out.print(call.get(1) + "----");
                    // }
                    if (call.get(0) != null && classes.contains(call.get(0))) {
                        System.out.print(call.get(1) + "----");
                    }
                });

                System.out.println("");
            });
        }
        catch (Exception e) {
            System.out.println("Error: " + e.getMessage());
        }
        
    }
}
