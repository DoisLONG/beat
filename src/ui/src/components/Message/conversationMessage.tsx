// Copyright (C) 2024 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { IconAi, IconUser, IconThumbUp, IconThumbUpFilled, IconThumbDown, IconThumbDownFilled } from "@tabler/icons-react"
import style from "./conversationMessage.module.scss"
import { ActionIcon, Group, Text } from "@mantine/core"
import { DateTime } from "luxon"
import { useState } from "react"
import Markdown from "../Markdown/Markdown"
import { TracedFileInfo } from "../../redux/Conversation/Conversation"
import { RetrieverRef } from "../Conversation/FileRef"
import { updateFeedback, conversationSelector } from '../../redux/Conversation/ConversationSlice'
import { useAppDispatch, useAppSelector } from '../../redux/store'
import { userSelector } from '../../redux/User/userSlice'
import { URL_FILE_DOWNLOAD } from '../../config';
import { IconLink } from "@tabler/icons-react"; // Use link icons from the Tabler icon library

export interface ConversationMessageProps {
  message: string
  human: boolean
  date: number
  onGoingState: string
  feedback?: string
  current_references?: TracedFileInfo[]
  history_index: number
}

export function ConversationMessage({ human, message, date, onGoingState, current_references, history_index }: ConversationMessageProps) {
  const dateFormat = () => {
    // console.log(date)
    // console.log(new Date(date))
    return DateTime.fromJSDate(new Date(date)).toLocaleString(DateTime.DATETIME_MED)
  }

  const [selected, setSelected] = useState<'good' | 'bad' | null>(null);
  const [openPanel, setOpenPanel] = useState(false);
  const [clickedIndex, setClickedIndex] = useState<number | null>(null);
  const dispatch = useAppDispatch();
  const { name } = useAppSelector(userSelector);
  const { selectedConversationId } = useAppSelector(conversationSelector)

  const handleClose = () => {
    setOpenPanel(false); // close panel
    setClickedIndex(null);
  };

  const handleOpen = (index: number) => {
    setClickedIndex(index);
    setOpenPanel(true);
  };

  const handleSelect = (type: 'good' | 'bad', index: number) => {
    if (index != -1) {
      dispatch(updateFeedback({type, index, name, selectedConversationId}));
    }
    setSelected(type === selected ? null : type);
  };

  
  // 处理message，在每个句号后添加换行
  // const processedMessage = message.replace(/。/g, '。\n');
  return (
    <div className={style.conversationMessage}>
      <Group>
        {/* <Avatar
          src="https://raw.githubusercontent.com/mantinedev/mantine/master/.demo/avatars/avatar-1.png"
          alt="Jacob Warnhalter"
          radius="xl"
        /> */}

        {human && <IconUser />}
        {!human && <IconAi />}

        <div>
          <Text size="sm">
            {human && "You"} {!human && "Assistant"}
          </Text>
          <Text size="xs" c="dimmed">
            {dateFormat()}
          </Text>
        </div>
      </Group>
      {/* <Text pl={54} pt="sm" size="sm">
        {human? message : (<Markdown content={message}/>)}
      </Text> */}
      <>
        {human ? (
          <Text pl={54} pt="sm" size="sm">
            {message}
          </Text>
        ) : (
      <div style={{ paddingLeft: '54px', paddingTop: "0px", fontSize: 'small'}}>
        <Markdown content={message} />
      </div>
        )}
      </>

      {/* panel to show retriever doc，only render when we get references */}
      {!human && onGoingState === "" && current_references && current_references.length > 0 && current_references.some(ref => ref.fileName !== undefined && ref.fileName !== "") && current_references.some(ref => ref.trainType !== undefined && ref.trainType !== "none") ? (
        <div style={{ paddingLeft: 54 }}>
          <Group gap={6} align="center" style={{ marginTop: 16, marginBottom: 12, alignItems: 'center' }}>
            <IconLink size={16} color="#666" />
            <Text size="md" style={{ fontWeight: 600, color: '#454545', fontSize: '14px', lineHeight: '16px' }}>
              来源：
            </Text>
          </Group>
          {current_references.map((ref, index) => {
            const isPdf = ref.fileName?.toLowerCase().endsWith('.pdf');
            
            // 根据trainType决定渲染逻辑
            if (ref.trainType === "total") {
              // trainType为total时保持原有逻辑
              return (
                <div key={index}>
                  {isPdf ? (
                    <a
                      href="#"
                      onClick={(e) => {
                        e.preventDefault();
                        handleOpen(index);
                      }}
                      style={{ textDecoration: 'underline', color: 'gray', cursor: 'pointer' }}
                    >
                      {ref.fileName} &#8599; {/* 斜向上的箭头符号 */}
                    </a>
                  ) : (
                    <a
                      href={URL_FILE_DOWNLOAD + decodeURIComponent(ref.filePath).trim()}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ textDecoration: 'underline', color: 'gray', cursor: 'pointer' }}
                    >
                      {ref.fileName} &#8599; {/* 斜向上的箭头符号 */}
                    </a>
                  )}
                  {isPdf && clickedIndex === index && (
                    <RetrieverRef
                      key={index}
                      opened={openPanel}
                      onClose={handleClose}
                      current_reference={ref}
                      history_index={history_index}
                    />
                  )}
                </div>
              );
            } else if (ref.trainType === "node") {
              // trainType为node时展示三个字符串拼接
              const concatenatedString = `${ref.fileName || ''} ${ref.rowId || ''} ${ref.position || ''}`;
              
              return (
                <div key={index} style={{ marginBottom: '8px', color: '#454545' }}>
                  {concatenatedString}
                </div>
              );
            } else {
              // 其他trainType情况，可以根据需要扩展或返回null
              return null;
            }
          })}
        </div>
      ) : (
        <></>
      )}


    {!human && onGoingState === "" && current_references && current_references.length > 0 ? (

        <div style={{ paddingLeft: 54 }}>
          {/* 网页链接标题 (type=2) */}
          {current_references.some(ref => ref.mcp && ref.mcp.length > 0) && (
            <Group gap={6} align="center" style={{ marginTop: 16, marginBottom: 12, alignItems: 'center' }}>
              <IconLink size={16} color="#666" />
              <Text size="md" style={{ fontWeight: 600, color: '#454545', fontSize: '14px', lineHeight: '16px' }}>
                mcp来源：
              </Text>
            </Group>
          )}
          
          {/* 网页链接列表 (type=2) */}
          {(() => {
            const firstRef = current_references[0];
            const mcpList = Array.isArray(firstRef?.mcp) ? firstRef.mcp : [];
            
            return mcpList.map((tool, toolIndex) => (
              <div key={`mcp-0-${toolIndex}`} style={{ marginBottom: '8px' }}>
                <div style={{ display: 'block', gap: '10px', fontSize: '0.9em', alignItems: 'flex-start', wordBreak: 'break-word', flexWrap: 'wrap' }}>
                  <span style={{ display: "block" }}>工具名称 : {tool?.name ?? 'N/A'}</span>
                  <span style={{ display: "block" }}>
                    工具结果 : {tool.result ? (
                      <span dangerouslySetInnerHTML={{
                        __html: tool.result.replace(/<\/?b>/g, '').replace(/\\n/g, '\n').replace(/\n/g, '<br />')
                      }} />
                    ) : ""}
                  </span>
                </div>
                <hr style={{ margin: '8px 0', border: 'none', borderTop: '1px solid #e0e0e0' }} />
              </div>
            ));
          })()}
        </div>
      ) : null}

      {!human && onGoingState === "" ? (
        <Group gap={"sm"} justify="flex-end">
          <Text size="sm" fs="italic" >Feedback:  </Text>
          <ActionIcon variant='light' onClick={() => handleSelect('good', history_index)}>
            {selected === 'good' ? <IconThumbUpFilled /> : <IconThumbUp />}
          </ActionIcon>
          <ActionIcon variant='light' onClick={() => handleSelect('bad', history_index)}>
            {selected === 'bad' ? <IconThumbDownFilled /> : <IconThumbDown />}
          </ActionIcon>
        </Group>
      ) : (
        <></>
      )}
      {/* <div className={style.header}>
        {human && <IconUser />}
        {!human && <IconAi />}
      </div>

      <div className={style.message}>{message}</div> */}
    </div>
  )
}
