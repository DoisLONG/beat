// Copyright (C) 2024 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { Title, ActionIcon, Box, Group, Collapse, Switch, Combobox, Input, InputBase, useCombobox, Select,
  Loader } from "@mantine/core"

import contextStyles from "../../styles/components/context.module.scss"
import { useAppDispatch, useAppSelector } from "../../redux/store"
import { conversationSelector,setSelectedDynamicOption, deleteConversation, getConversationHistory, setSelectedConversationId, setSelectedCollection, deleteLocalConversation, newConversation, setMcpList, } from "../../redux/Conversation/ConversationSlice"
import { userSelector } from "../../redux/User/userSlice"
import { useEffect, useState } from "react"
import { IconTrash, IconCaretDownFilled } from "@tabler/icons-react"
import { Tooltip, Button, Text} from '@mantine/core'
import { IconMessagePlus } from '@tabler/icons-react'
import {
URL_EXCELS
} from "../../config";
// import { uuidv4 } from "../../common/common"

// 定义 API 响应数据的类型
interface ApiResponse {
  status: number;
  msg: string;
  results: string[]; // data 是一个字符串数组
}

export interface ConversationContextProps {
    title: string
    historyOption: boolean
    setHistoryOption: any
}


export function ConversationSideBar({ title, historyOption, setHistoryOption }: ConversationContextProps) {
    const { conversations, selectedConversationId, collections, mcpList, selectedCollection,selectedDynamicOption, onGoingResult } = useAppSelector(conversationSelector)
    const { name } = useAppSelector(userSelector)
    const dispatch = useAppDispatch()
    const [ chatSetting, setChatSetting ] = useState(true);
    const [ collectionSetting, setCollectionSetting ] = useState(true);

    // 新增状态：动态下拉框的选项和加载状态
    const [dynamicOptions, setDynamicOptions] = useState<{value: string, label: string}[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    // const [selectedDynamicOption, setSelectedDynamicOption] = useState<string | null>('');
    

    // const [ mcpSetting, setMcpSetting ] = useState(false);

    useEffect(() => {
        if (selectedConversationId != "") {
            dispatch(getConversationHistory({ user: name, conversationId: selectedConversationId }))
                // 生成新的Session ID并更新
            // dispatch(setCurrentSessionId(uuidv4())); 
        }
    }, [selectedConversationId])

    // 监听selectedCollection的变化
    useEffect(() => {
        // 如果selectedCollection为空或者是SKIP，则清空动态选项
        if (selectedCollection === "SKIP" || selectedCollection === "") {
        setDynamicOptions([]);
        setSelectedDynamicOption('');
        return;
        }
        
        // 获取动态选项数据
        const fetchDynamicOptions = async () => {
        setIsLoading(true);
        try {
            // 调用后端API，传递selectedCollection作为参数
            const response = await fetch(URL_EXCELS, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json', // 根据API需求调整Content-Type
                    // 可以添加其他需要的headers，如认证token等
                },
                // 如果需要请求体，取消下面的注释并添加相应数据
                // body: JSON.stringify({ key: 'value' })
            });
            const result: ApiResponse = await response.json();
            
            // 检查响应码是否为200
            if (result.status === 200) {
            // 将API返回的数据转换为下拉框选项格式
            const formattedOptions = result.results.map((item: string) => ({
                value: item,
                label: item
            }));
            
            setDynamicOptions(formattedOptions);
            } else {
            console.error('API returned error:', result.msg);
            setDynamicOptions([]);
            }
        } catch (error) {
            console.error('Failed to fetch dynamic options:', error);
            setDynamicOptions([]);
        } finally {
            setIsLoading(false);
        }
        };
        
        fetchDynamicOptions();
    }, [selectedCollection]);
    
    // useEffect(() => {
    //     localStorage.removeItem('webSearchEnabled'); // 清除 localStorage
    //     dispatch(setWebSearch(false)); // 重置 Redux 状态
    //   }, [dispatch]);

    const handleDeleteConversation = (id: string) => {
        dispatch(deleteConversation({ user: name, conversationId: id }))
        dispatch(deleteLocalConversation(id))
    }

    const handleNewConversation = () => {
        dispatch(newConversation())
        setHistoryOption(false)
    }

    const conversationList = conversations?.map((curr) => (
        <div
            className={contextStyles.contextListItem}
            data-active={selectedConversationId === curr.id || undefined}
            onClick={(event) => {
                event.preventDefault()
                dispatch(setSelectedConversationId(curr.id))
                const selectedConversation = conversations.find(x=>x.id===curr.id)
                if ( selectedConversation !== undefined ) {
                    setHistoryOption(selectedConversation.current_prompt_only)
                }
            }}
            key={curr.id}
        >
            <div className={contextStyles.contextItemName} title={curr.first_query}>{curr.first_query}</div>
            {selectedConversationId === curr.id && (
                <ActionIcon onClick={() => handleDeleteConversation(curr.id)} size={30} variant="default">
                    <IconTrash />
                </ActionIcon>
            )}
        </div>
    ))

    const combobox = useCombobox({
        onDropdownClose: () => combobox.resetSelectedOption(),
      });

      const options = Object.entries(collections).map(([key, value]) => (
        <Combobox.Option value={key} key={value}>
          {key}
        </Combobox.Option>
    ));

    const handleToggle = (type: string) => {
        if (type === "collection") {
            setCollectionSetting(!collectionSetting)
        } else if (type === "chat") {
            setChatSetting(!chatSetting)
        }
    }

    
    // const mcpListWithMaps = mcpList.map(option => new Map(Object.entries(option)));
    return (
        <div className={contextStyles.contextWrapper}>
            <Title order={3} className={contextStyles.contextTitle}>
                {title}
            </Title>
            <div className={contextStyles.contextList}>{conversationList}</div>

            <div className={contextStyles.newConversationSettings}>
                <Tooltip label="New Conversation">
                <Button
                    onClick={handleNewConversation}
                    disabled={onGoingResult != ""}
                    variant="subtle" // remove border
                    className={contextStyles.newConversationSettings}
                >
                    Start a New Chat
                    <IconMessagePlus style={{ marginLeft: 8 }} />
                </Button>
                </Tooltip>
            </div>


            {/* 新增 Web Search 开关 */}
            <div className={contextStyles.contextSettings}>
                <Text size="lg" fw={500} mb="md">Tool Configuration</Text>
                {mcpList
                    .filter((option) => {
                    if (selectedCollection === "SKIP" || selectedCollection === "") {
                        return true; // 显示所有数据
                    } else {
                        return option.flag === "RAG"; // 过滤掉 flag !== "rag" 的数据
                    }
                    })
                    .map((option) => (
                    <Box key={option.tool_path} maw={400} mr="8px" mb="20px">
                        <Group justify="space-between" align="center" mb={5}>
                        <Text size="sm">{option.tool_name}</Text>
                        <Switch
                            checked={option.enabled}
                            onChange={() => {
                            dispatch(setMcpList(option.tool_path));
                            }}
                            color="blue"
                        />
                        </Group>
                    </Box>
                    ))}
                

                <Box maw={400} mr="8px" mb="20px">
                    <Group style={{ justifyContent: 'space-between', width: '100%' }} align="center" mb={5}>
                        <span className={contextStyles.configSubFont}>Knowledge Base</span>
                    </Group>

                    <div style={{ marginRight: "8px"}}>
                        <Combobox
                            store={combobox}
                            withinPortal={false}
                            onOptionSubmit={(val) => {
                                dispatch(setSelectedCollection(val));
                                // dispatch(setMcpList(val));
                                combobox.closeDropdown();
                            }}
                        >
                            <Combobox.Target>
                                <InputBase
                                    component="button"
                                    type="button"
                                    pointer
                                    rightSection={<Combobox.Chevron />}
                                    onClick={() => combobox.toggleDropdown()}
                                    rightSectionPointerEvents="none"
                                >
                                    { selectedCollection || <Input.Placeholder>Pick DataSet</Input.Placeholder>}
                                </InputBase>
                            </Combobox.Target>

                            <Combobox.Dropdown style={{ width: '12vw'}}>
                                <Combobox.Options>
                                    <Combobox.Option value="SKIP" key="SKIP">[&nbsp;SKIP&nbsp;]</Combobox.Option>
                                    {options}
                                </Combobox.Options>
                            </Combobox.Dropdown>
                        </Combobox>
                    </div>
                </Box>

                {/* 新增的动态下拉框 */}
                {selectedCollection && selectedCollection !== "SKIP" && (
                <Box maw={400} mr="8px" mb="20px">
                    <Group style={{ justifyContent: 'space-between', width: '100%' }} align="center" mb={5}>
                    <span className={contextStyles.configSubFont}>Dynamic Options</span>
                    </Group>
                    
                    <div style={{ marginRight: "8px", position: 'relative' }}>
                    <Select
                        value={selectedDynamicOption}
                        onChange={(value) => {
                        // 更新本地状态
                        setSelectedDynamicOption(value);
                        // 传递到 Redux store
                        dispatch(setSelectedDynamicOption(value));
                        }}
                        placeholder={isLoading ? "Loading options..." : "Select an option"}
                        data={dynamicOptions}
                        rightSection={isLoading ? <Loader size="xs" /> : null}
                        disabled={isLoading || dynamicOptions.length === 0}
                    />
                    </div>
                </Box>
                )}


                {/* use false to disable chat configuration, maybe need it again */}
                {false && (
                <Box maw={400} mr="8px" mb="20px">
                    <Group style={{ justifyContent: 'space-between', width: '100%' }} align="center" mb={5}>
                        <span className={contextStyles.configSubFont}>Chat Configuration</span>
                        <ActionIcon variant='light' onClick={() => handleToggle("chat")}>
                            <IconCaretDownFilled />
                        </ActionIcon>
                    </Group>

                    <Collapse in={chatSetting}>
                        <Switch
                            checked={historyOption}
                            label="Current Prompt Only"
                            onChange={(event) => {
                                setHistoryOption(event.currentTarget.checked)
                            }}
                        />
                    </Collapse>
                </Box>
                )}
            </div>
        </div>
    )
}
