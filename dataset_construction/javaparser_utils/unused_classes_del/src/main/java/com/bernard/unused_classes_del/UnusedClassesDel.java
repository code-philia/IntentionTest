package com.bernard.unused_classes_del;

import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.visitor.VoidVisitorAdapter;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.ast.expr.ObjectCreationExpr;
import com.github.javaparser.resolution.declarations.ResolvedMethodDeclaration;
import com.github.javaparser.symbolsolver.resolution.typesolvers.CombinedTypeSolver;
import com.github.javaparser.symbolsolver.JavaSymbolSolver;
import com.github.javaparser.resolution.TypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.ReflectionTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.JavaParserTypeSolver;
import com.github.javaparser.resolution.declarations.ResolvedReferenceTypeDeclaration;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;

import java.io.File;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Some code that uses JavaParser.
 */
public class UnusedClassesDel {
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
        private Map<String, List<String>> methodClassesInvoked = new HashMap<>();
    
        @Override
        public void visit(MethodDeclaration md, Void arg) {
            super.visit(md, arg);

            List<String> temp = new ArrayList<>();

            ResolvedMethodDeclaration rmdCaller = md.resolve();

            String callerMethod = getInternalRepresentation(rmdCaller);

            String mainClassName = md.resolve().getClassName();

            temp.add(mainClassName);

            List<List<String>> calls = new ArrayList<>();
    
            md.findAll(MethodCallExpr.class).forEach(mc -> {
                try {
                    // System.out.println("Method Call: " + mc.getNameAsString());
                    ResolvedMethodDeclaration rmdCallee = mc.resolve();

                    String className = rmdCallee.getClassName();

                    temp.add(className);

                    calls.add(temp);
                } catch (Exception e) {
                    // System.out.println("Error: " + e.getMessage());
                    // just ignore
                }
            });

            md.findAll(ObjectCreationExpr.class).forEach(oc -> {
                try {
                    String className = oc.resolve().getClassName();
                    temp.add(className);
                } catch (Exception e) {
                    // just ignore
                }
            });

            methodClassesInvoked.put(callerMethod, temp);
        }
    
        public Map<String, List<String>> getMethodClassesInvoked() {
            return methodClassesInvoked;
        }
    }

    private static class ClassVisitor extends VoidVisitorAdapter<Void> {
        private final Map<String, ClassDetails> classDetailsMap;

        public ClassVisitor(Map<String, ClassDetails> classDetailsMap) {
            this.classDetailsMap = classDetailsMap;
        }

        @Override
        public void visit(ClassOrInterfaceDeclaration n, Void arg) {
            super.visit(n, arg);

            // Get class name
            try {
                
            } catch (Exception e) {
                // just ignore
                return;
            }
            String className = n.resolve().getClassName();

            // Get starting and ending line numbers including annotations
            int startLine = n.getRange().map(range -> range.begin.line).orElse(-1);
            int endLine = n.getRange().map(range -> range.end.line).orElse(-1);

            // Save details in the map
            classDetailsMap.put(className, new ClassDetails(startLine, endLine));
        }
    }

    private static class ClassDetails {
        private final int startLine;
        private final int endLine;

        public ClassDetails(int startLine, int endLine) {
            this.startLine = startLine;
            this.endLine = endLine;
        }

        public int getStartLine() {
            return startLine;
        }

        public int getEndLine() {
            return endLine;
        }
    }

    static JavaSymbolSolver mainSymbolSolver = null;

    static JavaSymbolSolver alternateSymbolSolver = null;

    public static void main(String[] args) {
        String path = args[0];

        // // mainJavaPath is path, where the part after /src/main/java/ is deleted
        // String mainJavaPath = path.contains("/src/main/java/") 
        //     ? path.substring(0, path.indexOf("/src/main/java/") + 14) 
        //     : path.substring(0, path.indexOf("/src/test/java/") + 14);

        // // Set up a combined type solver that includes reflection and JavaParser
        // TypeSolver typeSolver = new CombinedTypeSolver(
        //     new ReflectionTypeSolver(),
        //     new JavaParserTypeSolver(new File(mainJavaPath)) // Adjust the path accordingly
        // );

        // // Set up the JavaSymbolSolver with the type solver
        // JavaSymbolSolver symbolSolver = new JavaSymbolSolver(typeSolver);

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
            // File file = new File(path);

            // StaticJavaParser
            //     .getParserConfiguration()
            //     .setSymbolResolver(symbolSolver);

            // CompilationUnit cu = StaticJavaParser.parse(file);

            File file = new File(path);

            StaticJavaParser
                .getParserConfiguration()
                .setSymbolResolver(mainSymbolSolver);

            CompilationUnit cu = StaticJavaParser.parse(file);

            StaticJavaParser
                    .getParserConfiguration()
                    .setSymbolResolver(alternateSymbolSolver);

            CompilationUnit cu2 = StaticJavaParser.parse(file);

            Map<String, ClassDetails> classDetailsMap = new HashMap<>();

            ClassVisitor classVisitor = new ClassVisitor(classDetailsMap);

            try {
                classVisitor.visit(cu, null);
            } catch (Exception e) {
                try {
                    classVisitor.visit(cu2, null);
                } catch (Exception e2) {
                    throw e2;
                }
            }

            // classVisitor.visit(cu, null);

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

            // methodCallVisitor.visit(cu, null);

            Map<String, List<String>> methodClasses = methodCallVisitor.getMethodClassesInvoked();

            Map<String, List<String>> methodToDeleteLines = new HashMap<>();

            for (Map.Entry<String, List<String>> entry : methodClasses.entrySet()) {
                String methodName = entry.getKey();
                List<String> classes = entry.getValue();

                List<String> deleteLines = new ArrayList<>();

                // for key in classDetailsMap (for all classes in the file)
                for (String className : classDetailsMap.keySet()) {
                    // If it's not used by the method
                    if (!classes.contains(className)) {
                        boolean isEnclosingClass = false;
                        // Check if it's an enclosing class
                        for (String classUsed : classes) {
                            if (classUsed.startsWith(className + '.')) {
                                isEnclosingClass = true;
                                break;
                            }
                        }
                        if (isEnclosingClass) {
                            continue;
                        }
                        int startLine = classDetailsMap.get(className).getStartLine();
                        int endLine = classDetailsMap.get(className).getEndLine();
                    
                        deleteLines.add(startLine + "-" + endLine);
                    }
                }

                methodToDeleteLines.put(methodName, deleteLines);
            }

            // Print methodToDeleteLines succinctly
            for (Map.Entry<String, List<String>> entry : methodToDeleteLines.entrySet()) {
                System.out.print(entry.getKey() + "////");

                for (String line : entry.getValue()) {
                    System.out.print(line + ",,,,");
                }

                System.out.println("");
            }
        }
        catch (Exception e) {
            System.out.println("Error: " + e.getMessage());
        }
    }
}
