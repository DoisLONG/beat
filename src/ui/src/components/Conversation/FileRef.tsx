// Copyright (C) 2024 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { Modal } from '@mantine/core'
import {
  AreaHighlight,
  Highlight,
  PdfHighlighter,
  PdfLoader,
  Popup,
} from "react-pdf-highlighter";
import type {
  Content,
  IHighlight,
  ScaledPosition,
} from "react-pdf-highlighter";
import {
  useEffect,
  useCallback,
  useRef,
} from "react";
import { Spinner } from "./Spinner";
import "react-pdf-highlighter/dist/style.css"
import { TracedFileInfo } from "../../redux/Conversation/Conversation"
import { URL_FILE_DOWNLOAD } from '../../config';


interface RetrieverRefProps {
  opened: boolean;
  onClose: () => void;
  current_reference?: TracedFileInfo;
  history_index?: number;
}

type PdfViewerProps = {
  history_index?: number;
  current_reference?: TracedFileInfo;
}

type LoaderProps = {
  pdfPath: string
  highlights: IHighlight[]
  setHighlights?: any
}

const Loader = ({ pdfPath, highlights, setHighlights }: LoaderProps) => {
  const parseIdFromHash = () =>
      document.location.hash.slice("#highlight-".length);

  const resetHash = () => {
      document.location.hash = "";
  };

  const HighlightPopup = ({
      comment,
    }: {
      comment: { text: string; emoji: string };
    }) =>
      comment.text ? (
        <div className="Highlight__popup">
          {comment.emoji} {comment.text}
        </div>
  ) : null;

  const scrollViewerTo = useRef((highlight: IHighlight) => {
    if (false) {
      console.log("current highlight: ", {highlight});
    }
  });

  const scrollToHighlightFromHash = useCallback(() => {
    const highlight = getHighlightById(parseIdFromHash());
    if (highlight) {
      scrollViewerTo.current(highlight);
    }
  }, [highlights]);

  const getHighlightById = (id: string) => {
    return highlights.find((highlight: IHighlight) => highlight.id === id);
  };

  
  useEffect(() => {
    if (highlights.length > 0) {
      document.location.hash = `highlight-${highlights[0].id}`;
    }
  },[highlights])

  useEffect(() => {
    window.addEventListener("hashchange", scrollToHighlightFromHash, false);
    return () => {
      window.removeEventListener(
        "hashchange",
        scrollToHighlightFromHash,
        false,
      );
    };
  }, [scrollToHighlightFromHash]);


  const updateHighlight = (
    highlightId: string,
    position: Partial<ScaledPosition>,
    content: Partial<Content>,
  ) => {
    console.log("Updating highlight", highlightId, position, content);
    setHighlights((prevHighlights: IHighlight[]) =>
      prevHighlights.map((h: IHighlight) => {
        const {
          id,
          position: originalPosition,
          content: originalContent,
          ...rest
        } = h;
        return id === highlightId
          ? {
              id,
              position: { ...originalPosition, ...position },
              content: { ...originalContent, ...content },
              ...rest,
            }
          : h;
      }),
    );
  };

  return(
    <PdfLoader url={pdfPath}
       beforeLoad={<Spinner />}
       workerSrc='/assets/js/pdf.worker.min.js'>
        {(pdfDocument) => (
            <PdfHighlighter
              pdfDocument={pdfDocument}
              enableAreaSelection={() => false}
              onScrollChange={resetHash}
              scrollRef={(scrollTo) => {
                scrollViewerTo.current = scrollTo;
                scrollToHighlightFromHash();
              }}
              onSelectionFinished={() => { return null;}}
              highlightTransform={(
                highlight,
                index,
                setTip,
                hideTip,
                viewportToScaled,
                screenshot,
              ) => {
                const isTextHighlight = !highlight.content?.image;
                const isScrolledTo = false
                const component = isTextHighlight ? (
                  <Highlight
                    isScrolledTo={isScrolledTo}
                    position={highlight.position}
                    comment={highlight.comment}
                  />
                ) : (
                  <AreaHighlight
                    isScrolledTo={isScrolledTo}
                    highlight={highlight}
                    onChange={(boundingRect) => {
                      updateHighlight(
                        highlight.id,
                        { boundingRect: viewportToScaled(boundingRect) },
                        { image: screenshot(boundingRect) },
                      );
                    }}
                  />
              );

              return (
                <Popup
                  popupContent={<HighlightPopup {...highlight} />}
                  onMouseOver={(popupContent) =>
                    setTip(highlight, (_highlight) => popupContent)
                  }
                  onMouseOut={hideTip}
                  key={index}
                >
                {component}
                </Popup>
              );
              }}
              highlights={highlights}
            />
        )}
    </PdfLoader>
  );
};

const SinglePdfViewer = ({ current_reference } : PdfViewerProps) => {
  let referenceFile = current_reference?.filePath as string
  let referenceHighlight = current_reference?.reference as IHighlight[]
  let pdfPath = (URL_FILE_DOWNLOAD + decodeURIComponent(referenceFile).trim())

  return (
      <div style={{ display: "flex", height: "100vh" }}>
      {/* <div style={{ height: "100vh", width: "75vw", position: "relative", borderLeft: "3px solid var(--mantine-color-gray-1)"}}> */}
      <div style={{ height: "100vh", width: "75vw", position: "relative", borderLeft: "3px solid var(--mantine-color-gray-1)", borderRight: "3px solid var(--mantine-color-gray-1)" }}>
        {referenceFile ? (
          <Loader pdfPath={pdfPath} highlights={referenceHighlight} />
        ):(
          <></>
        )}
      </div>
      </div>
  );
}

export function RetrieverRef({ opened, onClose, history_index, current_reference }: RetrieverRefProps) {
  let title = current_reference?.fileName

  return (
    <Modal
      title={<span style={{ color: 'black', fontSize: '24px', fontWeight: 'bold', fontFamily: 'Greycliff CF' }}>{title}</span>}
      size="75%"
      opened={opened}
      onClose={onClose}
    >
      <div style={{ borderBottom: "5px solid gray", marginBottom: "16px" }}></div>
      <SinglePdfViewer
        history_index={history_index}
        current_reference={current_reference}
      />
    </Modal>
  );
}
