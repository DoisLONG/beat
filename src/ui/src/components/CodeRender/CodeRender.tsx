import styles from './codeRender.module.scss'
//@ts-ignore
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
//@ts-ignore
import { tomorrow } from "react-syntax-highlighter/dist/esm/styles/prism";
import { IconCopy } from '@tabler/icons-react';
import { Button, CopyButton } from '@mantine/core';

type CodeRenderProps = {
    cleanCode: React.ReactNode,
    language: string,
    inline: boolean
}
const CodeRender = ({ cleanCode, language, inline}:CodeRenderProps) => {
    //cleanCode = String(cleanCode).replace(/^\s*[\r\n]/gm, '').replace(/\n*$/, '\n') //right trim and remove empty lines from the input
    cleanCode = String(cleanCode).replace(/^\s*[\r]/gm, '')
    // console.log(styles)
    try {
        return !inline && language ? (
            <div className={styles.code}>
                <div className={styles.codeHead}>
                    <div className='code-title'>
                        {language}
                    </div>
                    <div className={styles.codeActionGroup} >
                        <CopyButton value={cleanCode.toString()}>
                            {({ copied, copy }) => (
                                <Button color={copied ? 'teal' : 'blue'} styles={{root:{border:"none"}}} leftSection={<IconCopy size={12} />} onClick={copy}>
                                    {copied ? 'Copied' : 'Copy'}
                                </Button>
                            )}
                        </CopyButton>
                    </div>
                </div>
                <SyntaxHighlighter
                    className={styles.codeHighlighterDiv}
                    children={cleanCode.toString()}
                    wrapLongLines={true}
                    style={tomorrow}
                    language={language}
                    PreTag="div"
                />
            </div>
        ):(
            <code className='inline-code'><i>{cleanCode}</i></code>
        )
    } catch (err) {
        return (
            <pre>
                {cleanCode}
            </pre>
        )
    }

}

export default CodeRender;