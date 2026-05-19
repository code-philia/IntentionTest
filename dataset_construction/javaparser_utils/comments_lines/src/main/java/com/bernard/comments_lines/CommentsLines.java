package com.bernard.comments_lines;

import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.visitor.VoidVisitorAdapter;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.StaticJavaParser;
import com.github.javaparser.ast.expr.BinaryExpr;
import com.github.javaparser.ast.stmt.IfStmt;
import com.github.javaparser.ast.stmt.Statement;
import com.github.javaparser.ast.visitor.ModifierVisitor;
import com.github.javaparser.ast.visitor.Visitable;
import com.github.javaparser.utils.CodeGenerationUtils;
import com.github.javaparser.utils.Log;
import com.github.javaparser.ast.comments.Comment;
import com.github.javaparser.ast.comments.LineComment;
import com.github.javaparser.ast.comments.BlockComment;
import com.github.javaparser.ast.comments.JavadocComment;
import com.github.javaparser.utils.SourceRoot;

import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.io.File;

/**
 * Some code that uses JavaParser.
 */
public class CommentsLines {
    // private static class MethodLineVisitor extends VoidVisitorAdapter {
    //     @Override
    //     public void visit(Comment md, Object arg) {
    
    //         System.out.println(md.getName() + " " + md.getRange().get().begin.line + " " + md.getRange().get().end.line);
    
    //     }
    // }

    public static void main(String[] args) {
        String path = args[0];
        try {
            File sourceFile = new File(path);
            CompilationUnit cu = StaticJavaParser.parse(sourceFile);
            // new MethodLineVisitor().visit(cu, null);

            // Collect all comment lines
            Set<Integer> blockComments = new HashSet<>();
            for (Comment comment : cu.getAllComments()) {
                if (comment instanceof BlockComment || comment instanceof JavadocComment) {
                    int beginLine = comment.getBegin().get().line;
                    int endLine = comment.getEnd().get().line;
                    for (int i = beginLine; i <= endLine; i++) {
                        blockComments.add(i);
                    }
                }
            }

            // print commentLines
            // for (int line : blockComments) {
            //     System.out.println("Line " + line);
            // }

            // Read the source file lines
            List<String> lines = java.nio.file.Files.readAllLines(Paths.get(sourceFile.toURI()));

            // Identify lines that are 100% comments
            List<Integer> fullyCommentedLines = new ArrayList<>();
            for (int i = 0; i < lines.size(); i++) {
                int lineNumber = i + 1;
                String line = lines.get(i).trim();
                if (line.startsWith("//") || blockComments.contains(lineNumber)) {
                    fullyCommentedLines.add(lineNumber);
                }
            }

            // Output the lines that are 100% comments
            for (int line : fullyCommentedLines) {
                System.out.println(line);
            }
        }
        catch (Exception e) {
            System.out.println("Error: " + e.getMessage());
        }
        
    }
}


