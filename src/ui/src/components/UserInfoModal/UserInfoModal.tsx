// Copyright (C) 2024 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { SyntheticEvent, useEffect, useState } from 'react'
import { useDisclosure } from '@mantine/hooks';
import { TextInput, Button, Modal } from '@mantine/core';
import { useDispatch, useSelector } from 'react-redux';
import { useAppDispatch } from '../../redux/store'
import { userSelector, setUser } from '../../redux/User/userSlice';
import { getCollections, getMcpList } from '../../redux/Conversation/ConversationSlice';


const UserInfoModal = () => {
    const [opened, { open, close }] = useDisclosure(false);
    const { name } = useSelector(userSelector);
    const [username, setUsername] = useState(name || "");
    
    // set user as 'Anonymous' by default
    const dispatch = useDispatch();
    dispatch(setUser("Anonymous"))

    const handleSubmit = (event: SyntheticEvent) => {
        event.preventDefault()
        if(username){
            close();
            dispatch(setUser(username));
            setUsername("");
            const conversationdispatch = useAppDispatch();
            conversationdispatch(getCollections(undefined));
            conversationdispatch(getMcpList(undefined));
        }
        
    }
    useEffect(() => {
        // Disable login by default now
        // if (!name) {
        if (false) {
            open();
        }
    }, [])
    return (
        <>
            <Modal opened={opened} withCloseButton={false} onClose={()=>handleSubmit} title="Tell us who you are ?" centered>
                <>
                    <form onSubmit={handleSubmit} >
                        <TextInput label="Username" placeholder="Username" onChange={(event)=> setUsername(event?.currentTarget.value)} value={username} data-autofocus />
                        <Button fullWidth onClick={handleSubmit} mt="md">
                            Submit
                        </Button>
                    </form>
                    
                </>
            </Modal>
        </>

    )
}

export default UserInfoModal