package com.bernard.method_lines;

import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.visitor.VoidVisitorAdapter;
import com.github.javaparser.resolution.TypeSolver;
import com.github.javaparser.symbolsolver.JavaSymbolSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.CombinedTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.JavaParserTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.ReflectionTypeSolver;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.resolution.TypeSolver;
import com.github.javaparser.resolution.declarations.ResolvedMethodDeclaration;
import com.github.javaparser.symbolsolver.resolution.typesolvers.CombinedTypeSolver;
import com.github.javaparser.symbolsolver.JavaSymbolSolver;

import com.github.javaparser.symbolsolver.resolution.typesolvers.ReflectionTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.JavaParserTypeSolver;


import java.io.File;

/**
 * Some code that uses JavaParser.
 */
public class MethodLines {
    private static class MethodLineVisitor extends VoidVisitorAdapter {
        @Override
        public void visit(MethodDeclaration md, Object arg) {
            String className = md.resolve().getClassName();
    
            System.out.println(className + "::::" + md.getName() + " " + md.getRange().get().begin.line + " " + md.getRange().get().end.line);
    
        }
    }
    public static void main(String[] args) {
        String path = args[0];

        String mainJavaPath = path.contains("/src/main/java/") 
            ? path.substring(0, path.indexOf("/src/main/java/") + 14) 
            : path.substring(0, path.indexOf("/src/test/java/") + 14);

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
