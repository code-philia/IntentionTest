import "./index.css"
import SyntaxHighlighter from 'react-syntax-highlighter';
import { docco } from 'react-syntax-highlighter/dist/esm/styles/hljs';

function FocalFile({ focalFile, currCovLines, label }) {
  return (
    <div className="focal_file">
      <h1>Focal File</h1>
      {focalFile && 
      <SyntaxHighlighter 
        className="focal_file_code"
        language="java" 
        theme={docco} 
        wrapLines 
        lineNumberStyle={{display: "none"}} 
        showLineNumbers 
        lineProps={(lineNumber) => {
          const style = { display: "block", width: "fit-content", style: {flexWrap: 'wrap'} };
          if (currCovLines?.includes(lineNumber)) {
            style.backgroundColor = "#FFDB81";
            return {style, onClick: () => label(lineNumber)};
          }
          return {style};
        }} 
        customStyle={{lineHeight: "1", fontSize: "13px"}} 
        codeTagProps={{style:{lineHeight: "inherit", fontSize: "inherit"}}}
      >
          {focalFile.join('')}
      </SyntaxHighlighter>}
    </div>
  );
}

export default FocalFile;