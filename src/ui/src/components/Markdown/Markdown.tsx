import markdownStyles from './markdown.module.scss';
import thinkBlockStyles from './thinkblock.module.scss';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkFrontmatter from 'remark-frontmatter';
import CodeRender from '../CodeRender/CodeRender';
import { useState } from 'react';
import { Button } from '@mantine/core';

type MarkdownProps = {
    content: string
}

// Custom component to handle <think> tags
const ThinkBlock = ({ content }: { content: string }) => {
    const [isVisible, setIsVisible] = useState(true);

    return (
        <div>
            <Button
                onClick={() => setIsVisible(!isVisible)}
                className={thinkBlockStyles.button}
            >
                Thinking Content {isVisible ? '↓' : '↑'} 
            </Button>
            {isVisible && (
                <div className={thinkBlockStyles.content}>
                    {content}
                </div>
            )}
        </div>
    );
};

const Markdown = ({ content }: MarkdownProps) => {
    //format the response to remove "\n" and "\t"
    const formattedText = content.replace(/\\n/g, '  \n').replace(/\\t/g, '    ').replace(/```markdown([\s\S]*?)```/g, '$1');
    // Preprocess the content to replace <think>...</think> with React components
    const preprocessContent = (text: string) => {
        const regex = /<think>([\s\S]*?)<\/think>/g;
        const elements: React.ReactNode[] = [];
        let lastIndex = 0;
        let match;

        while ((match = regex.exec(text)) !== null) {
            const thinkContent = match[1];
            const startIndex = match.index;

            // Add plain text before the <think> tag
            if (startIndex > lastIndex) {
                elements.push(text.slice(lastIndex, startIndex));
            }

            // Add the ThinkBlock component
            elements.push(<ThinkBlock key={startIndex} content={thinkContent} />);

            lastIndex = regex.lastIndex;
        }

        // Add remaining plain text after the last <think> tag
        if (lastIndex < text.length) {
            elements.push(text.slice(lastIndex));
        }

        return elements;
    };

    const processedContent = preprocessContent(formattedText);

    return (
        <div className={markdownStyles.md}>
            {processedContent.map((element, index) =>
                typeof element === 'string' ? (
                    <ReactMarkdown
                        key={index}
                        children={element}
                        remarkPlugins={[remarkGfm, remarkFrontmatter]}
                        components={{
                            p: ({ children, ...props }) => {
                                return (
                                    <p {...props} style={{ whiteSpace: "pre-wrap" }}>
                                        {children}
                                    </p>
                                );
                            },
                            a: ({ children, ...props }) => {
                                return (
                                    <a
                                        href={props.href}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        {...props}
                                    >
                                        {children}
                                    </a>
                                );
                            },
                            table: ({ children, ...props }) => {
                                return (
                                    <div
                                        className={markdownStyles.tableDiv}
                                        style={{
                                            overflowX: "auto",
                                            padding: "10px",
                                        }}
                                    >
                                        <table {...props}>{children}</table>
                                    </div>
                                );
                            },
                            //@ts-expect-error inline can undefined sometimes
                            code({ inline, className, children }) {
                                const lang = /language-(\w+)/.exec(className || '');
                                return <CodeRender cleanCode={children} inline={inline} language={(lang && lang[1]) || ""} />;
                            },
                        }}
                    />
                ) : (
                    element
                )
            )}
        </div>
    );
};

export default Markdown;