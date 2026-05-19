package com.bernard.method_lines;

import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.visitor.VoidVisitorAdapter;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.resolution.TypeSolver;
import com.github.javaparser.resolution.declarations.ResolvedMethodDeclaration;
import com.github.javaparser.symbolsolver.resolution.typesolvers.CombinedTypeSolver;
import com.github.javaparser.symbolsolver.JavaSymbolSolver;

import com.github.javaparser.symbolsolver.resolution.typesolvers.ReflectionTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.JavaParserTypeSolver;

import java.io.File;
import java.util.ArrayList;

/**
 * Some code that uses JavaParser.
 */
public class MethodLines {
    private static String getInternalRepresentation(ResolvedMethodDeclaration rmd) {
        String methodName = rmd.getName();
        ArrayList<String> parameters = new ArrayList<>();

        int noParams = rmd.getNumberOfParams();

        for (int i = 0; i < noParams; i++) {
            parameters.add(rmd.getParam(i).getType().describe());
            // parameters.add(rmd.getParam(i).getTypeAsString());
        }

        String className = rmd.getClassName();

        String fin = "";
        fin += className + "::::" + methodName + "(";
        // fin += methodName + "(";
        for (int i = 0; i < parameters.size(); i++) {
            fin += parameters.get(i);
            if (i < parameters.size() - 1) {
                fin += ",";
            }
        }
        fin += ")";

        return fin;
    }

    private static class MethodLineVisitor extends VoidVisitorAdapter {
        @Override
        public void visit(MethodDeclaration md, Object arg) {
            try {
                System.out.println(getInternalRepresentation(md.resolve()) + " " + md.getRange().get().begin.line + " " + md.getRange().get().end.line);
            } catch (Exception e) {
                // System.out.println("Error: " + e.getMessage());
                return;
            }
    
        }
    }

    public static void main(String[] args) {
        String path = args[0];

        // mainJavaPath is path, where the part after /src/main/java/ is deleted if it exists,
        // if /src/test/java/ exists instead, delete the part after that
        String mainJavaPath = path.contains("/src/main/java/") 
            ? path.substring(0, path.indexOf("/src/main/java/") + 14) 
            : path.substring(0, path.indexOf("/src/test/java/") + 14);

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
            new MethodLineVisitor().visit(cu, null);
        }
        catch (Exception e) {
            System.out.println("Error: " + e.getMessage());
        }
        
    }
}
