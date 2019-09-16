from __future__ import print_function

import os
import time

import dgl
import networkx as nx
import torch
import torchvision
from torch import nn, optim
from torch.utils.data import DataLoader
from tensorboardX import SummaryWriter
from sklearn.model_selection import train_test_split

import ipdb
import h5py
import pickle
import argparse
import numpy as np
from tqdm import tqdm
from PIL import Image, ImageDraw, ImageFont

import utils.io as io
from model.model import AGRNN
from datasets import metadata
from utils.vis_tool import vis_img
from datasets.hico_constants import HicoConstants
from datasets.hico_dataset import HicoDataset, collate_fn

###########################################################################################
#                                     TRAIN/TEST MODEL                                    #
###########################################################################################

def run_model(args, data_const):
    # set up dataset variable
    train_dataset = HicoDataset(data_const=data_const, subset='train')
    val_dataset = HicoDataset(data_const=data_const, subset='val')
    dataset = {'train': train_dataset, 'val': val_dataset}
    print('set up dataset variable successfully')
    # use default DataLoader() to load the data. 
    train_dataloader = DataLoader(dataset=dataset['train'], batch_size=args.batch_size, shuffle=True, collate_fn=collate_fn)
    val_dataloader = DataLoader(dataset=dataset['val'], batch_size=args.batch_size, shuffle=True, collate_fn=collate_fn)
    dataloader = {'train': train_dataloader, 'val': val_dataloader}
    print('set up dataloader successfully')

    device = torch.device('cuda' if torch.cuda.is_available() and args.gpu else 'cpu')
    print('training on {}...'.format(device))

    model = AGRNN(feat_type=args.feat_type, bias=args.bias, bn=args.bn, dropout=args.drop_prob)
    # load pretrained model
    if args.pretrained:
        print(f"loading pretrained model {args.pretrained}")
        checkpoints = torch.load(args.pretrained, map_location=device)
        model.load_state_dict(checkpoints['state_dict'])
    model.to(device)
    # # build optimizer && criterion  
    optimizer = optim.SGD(model.parameters(), lr=args.lr, momentum=0.9, weight_decay=0.0001)
    # optimizer = optim.Adam(model.parameters(), lr=args.lr, weight_decay=0)
    # ipdb.set_trace()
    # criterion = nn.MultiLabelSoftMarginLoss()
    criterion = nn.BCEWithLogitsLoss()
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=30, gamma=0.5) #the scheduler divides the lr by 10 every 150 epochs

    # get the configuration of the model and save some key configurations
    io.mkdir_if_not_exists(os.path.join(args.save_dir, args.exp_ver), recursive=True)
    for i in range(args.layers):
        if i==0:
            model_config = model.CONFIG1.save_config()
            model_config['lr'] = args.lr
            model_config['bs'] = args.batch_size
            model_config['layers'] = args.layers
            io.dump_json_object(model_config, os.path.join(args.save_dir, args.exp_ver, 'l1_config.json'))
        elif i==1:
            model_config = model.CONFIG2.save_config()
            io.dump_json_object(model_config, os.path.join(args.save_dir, args.exp_ver, 'l2_config.json'))
        else:
            model_config = model.CONFIG3.save_config()
            io.dump_json_object(model_config, os.path.join(args.save_dir, args.exp_ver, 'l3_config.json'))
    print('save key configurations successfully...')

    if args.train_model == 'epoch':
        epoch_train(model, dataloader, dataset, criterion, optimizer, scheduler, device, data_const)
    else:
        iteration_train(model, dataloader, dataset, criterion, optimizer, scheduler, device, data_const)

def epoch_train(model, dataloader, dataset, criterion, optimizer, scheduler, device, data_const):
    print('epoch training...')
    
    # set visualization and create folder to save checkpoints
    writer = SummaryWriter(log_dir=args.log_dir + '/' + args.exp_ver + '/' + 'epoch_train')
    io.mkdir_if_not_exists(os.path.join(args.save_dir, args.exp_ver, 'epoch_train'), recursive=True)

    for epoch in range(args.start_epoch, args.epoch):
        # each epoch has a training and validation step
        for phase in ['train', 'val']:
            start_time = time.time()
            running_loss = 0.0
            idx = 0

            for data in tqdm(dataloader[phase]): 
                train_data = data
                # ipdb.set_trace()
                img_name = train_data['img_name']
                det_boxes = train_data['det_boxes']
                roi_labels = train_data['roi_labels']
                roi_scores = train_data['roi_scores']
                node_num = train_data['node_num']
                node_labels = train_data['node_labels']
                features = train_data['features']
                spatial_feat = train_data['spatial_feat']
                node_one_hot = train_data['node_one_hot']
                # features, node_labels = torch.FloatTensor(features).to(device), torch.FloatTensor(node_labels).to(device)
                features, spatial_feat, node_one_hot, node_labels = features.to(device), spatial_feat.to(device), node_one_hot.to(device), node_labels.to(device)
               
                # if idx == 100: break    
                if phase == 'train':
                    model.train()
                    model.zero_grad()
                    outputs = model(node_num, features, spatial_feat, node_one_hot, roi_labels)
                    loss = criterion(outputs, node_labels.float())
                    loss.backward()
                    optimizer.step()
                else:
                    model.eval()
                    # turn off the gradients for validation, save memory and computations
                    with torch.no_grad():
                        outputs = model(node_num, features, spatial_feat, node_one_hot, roi_labels, validation=True)
                        loss = criterion(outputs, node_labels.float())

                    # print result every 1000 iterationa during validation
                    if idx==0 or idx % round(1000/args.batch_size)==round(1000/args.batch_size)-1:
                        # ipdb.set_trace()
                        image = Image.open(os.path.join(args.img_data, img_name[0])).convert('RGB')
                        image_temp = image.copy()
                        raw_outputs = nn.Sigmoid()(outputs[0:int(node_num[0])])
                        raw_outputs = raw_outputs.cpu().detach().numpy()
                        # class_img = vis_img(image, det_boxes, roi_labels, roi_scores)
                        class_img = vis_img(image, det_boxes[0], roi_labels[0], roi_scores[0], node_labels[0:int(node_num[0])].cpu().numpy(), score_thresh=0.7)
                        action_img = vis_img(image_temp, det_boxes[0], roi_labels[0], roi_scores[0], raw_outputs, score_thresh=0.7)
                        writer.add_image('gt_detection', np.array(class_img).transpose(2,0,1))
                        writer.add_image('action_detection', np.array(action_img).transpose(2,0,1))

                idx+=1
                # accumulate loss of each batch
                running_loss += loss.item() * node_labels.shape[0]
            # calculate the loss and accuracy of each epoch
            epoch_loss = running_loss / len(dataset[phase])
            
            # log trainval datas, and visualize them in the same graph
            if phase == 'train':
                train_loss = epoch_loss  
            else:
                writer.add_scalars('trainval_loss_epoch', {'train': train_loss, 'val': epoch_loss}, epoch)
            # print data
            if (epoch % args.print_every) == 0:
                end_time = time.time()
                # print("[{}] Epoch: {}/{} Loss: {} Acc: {} Execution time: {}".format(\
                #         phase, epoch+1, args.epoch, epoch_loss, epoch_acc, (end_time-start_time)))
                print("[{}] Epoch: {}/{} Loss: {} Execution time: {}".format(\
                        phase, epoch+1, args.epoch, epoch_loss, (end_time-start_time)))

        # scheduler.step()
        # save model
        if epoch % args.save_every == (args.save_every -1):
            checkpoint = { 
                            'lr': args.lr,
                           'b_s': args.batch_size,
                          'bias': args.bias, 
                            'bn': args.bn, 
                       'dropout': args.drop_prob,
                     'feat_type': args.feat_type,
                    'state_dict': model.state_dict()
            }
            save_name = "checkpoint_" + str(epoch+1) + '_epoch.pth'
            torch.save(checkpoint, os.path.join(args.save_dir, args.exp_ver, 'epoch_train', save_name))

    writer.close()
    print('Finishing training!')

def iteration_train(model, dataloader, dataset, criterion, optimizer, scheduler, device, data_const):
    print('iteration training...')

    # # set visualization and create folder to save checkpoints
    writer = SummaryWriter(log_dir=args.log_dir + '/' + args.exp_ver + '/' + 'iteration_train')
    io.mkdir_if_not_exists(os.path.join(args.save_dir, args.exp_ver, 'iteration_train'), recursive=True)
    iter=0
    for epoch in range(args.epoch):
        start_time = time.time()
        running_loss = 0.0
        for data in tqdm(dataloader['train']): 
            train_data = data
            img_name = train_data['img_name']
            det_boxes = train_data['det_boxes']
            roi_labels = train_data['roi_labels']
            roi_scores = train_data['roi_scores']
            node_num = train_data['node_num']
            node_labels = train_data['node_labels']
            features = train_data['features']   
            features, node_labels = features.to(device), node_labels.to(device)
            # training
            model.train()
            model.zero_grad()
            outputs = model(node_num, features, roi_labels)
            loss = criterion(outputs, node_labels.float())
            loss.backward()
            optimizer.step()
            # loss.backward()
            # if step%exp_const.imgs_per_batch==0:
            #     optimizer.step()
            #     optimizer.zero_grad()
            # accumulate loss of each batch
            running_loss += loss.item() * node_labels.shape[0]
            if iter % 99 == 0:
                loss = running_loss/(iter+1)
                writer.add_scalar('train_loss_iter', loss, iter)

            if iter % 4999 == 0:
                num_samples = 2500
                val_loss = 0
                idx = 0
                for data in tqdm(dataloader['val']):
                    train_data = data
                    img_name = train_data['img_name']
                    det_boxes = train_data['det_boxes']
                    roi_labels = train_data['roi_labels']
                    roi_scores = train_data['roi_scores']
                    node_num = train_data['node_num']
                    node_labels = train_data['node_labels']
                    features = train_data['features']   
        
                    features, node_labels = features.to(device), node_labels.to(device)
                    # training
                    model.eval()
                    model.zero_grad()
                    outputs = model(node_num, features, roi_labels, validation=True)
                    loss = criterion(outputs, node_labels.float())
                    val_loss += loss.item() * node_labels.shape[0]

                    if idx==0 or idx%1000 == 999:
                        image = Image.open(os.path.join(args.img_data, img_name[0])).convert('RGB')
                        image_temp = image.copy()
                        raw_outputs = nn.Sigmoid()(outputs[0:int(node_num[0])])
                        raw_outputs = raw_outputs.cpu().detach().numpy()
                        # class_img = vis_img(image, det_boxes, roi_labels, roi_scores)
                        class_img = vis_img(image, det_boxes[0], roi_labels[0], roi_scores[0], node_labels[0:int(node_num[0])].cpu().numpy())
                        action_img = vis_img(image_temp, det_boxes[0], roi_labels[0], roi_scores[0], raw_outputs)
                        writer.add_image('gt_detection', np.array(class_img).transpose(2,0,1))
                        writer.add_image('action_detection', np.array(action_img).transpose(2,0,1))
                    idx+=1
                loss = val_loss / len(dataset['val'])
                writer.add_scalar('val_loss_iter', loss, iter)
                
                # save model
                checkpoint = { 
                            'lr': args.lr,
                           'b_s': args.batch_size,
                          'bias': args.bias, 
                            'bn': args.bn, 
                       'dropout': args.drop_prob,
                     'feat_type': args.feat_type,
                    'state_dict': model.state_dict()
                }
                save_name = "checkpoint_" + str(iter+1) + '_iters.pth'
                torch.save(checkpoint, os.path.join(args.save_dir, args.exp_ver, 'iteration_train', save_name))

            iter+=1

        epoch_loss = running_loss / len(dataset['train'])
        if (epoch % args.print_every) == 0:
            end_time = time.time()
            # print("[{}] Epoch: {}/{} Loss: {} Acc: {} Execution time: {}".format(\
            #         phase, epoch+1, args.epoch, epoch_loss, epoch_acc, (end_time-start_time)))
            print("[{}] Epoch: {}/{} Loss: {} Execution time: {}".format(\
                    'train', epoch+1, args.epoch, epoch_loss, (end_time-start_time)))

    writer.close()
    print('Finishing training!')



###########################################################################################
#                                 SET SOME ARGUMENTS                                      #
###########################################################################################
# define a string2boolean type function for argparse
def str2bool(arg):
    arg = arg.lower()
    if arg in ['yes', 'true', '1']:
        return True
    elif arg in ['no', 'false', '0']:
        return False
    else:
        # raise argparse.ArgumentTypeError('Boolean value expected!')
        pass

parser = argparse.ArgumentParser(description="separable 3D CNN for action classification!")

parser.add_argument('--batch_size', '--b_s', type=int, default=2,
                    help='batch size: 2')
parser.add_argument('--layers', type=int, default=3, required=True,
                    help='the num of gcn layers: 3') 
parser.add_argument('--drop_prob', type=float, default=None,
                    help='dropout parameter: None')
parser.add_argument('--lr', type=float, default=0.001,
                    help='learning rate: 0.001')
parser.add_argument('--gpu', type=str2bool, default='true', 
                    help='chose to use gpu or not: True') 
parser.add_argument('--bias', type=str2bool, default='true',
                    help="add bias to fc layers or not: True")
parser.add_argument('--bn', type=str2bool, default='true',
                    help='use batch normailzation or not: true')
# parse.add_argument('--bn', action="store_true", default=False,
#                     help='visualize the result or not')
parser.add_argument('--clip', type=int, default=4,
                     help='gradient clipping: 4')

parser.add_argument('--img_data', type=str, default='datasets/hico/images/train2015',
                    help='location of the original dataset')
parser.add_argument('--pretrained', '-p', type=str, default=None,
                    help='location of the pretrained model file for training: None')
parser.add_argument('--log_dir', type=str, default='./log',
                    help='path to save the log data like loss\accuracy... : ./log') 
parser.add_argument('--save_dir', type=str, default='./checkpoints',
                    help='path to save the checkpoints: ./checkpoints')

parser.add_argument('--epoch', type=int, default=300,
                    help='number of epochs to train: 300') 
parser.add_argument('--start_epoch', type=int, default=0,
                    help='number of beginning epochs : 0') 
parser.add_argument('--print_every', type=int, default=10,
                    help='number of steps for printing training and validation loss: 10') 
parser.add_argument('--save_every', type=int, default=20,
                    help='number of steps for saving the model parameters: 50')                      
parser.add_argument('--test_every', type=int, default=50,
                    help='number of steps for testing the model: 50')  

parser.add_argument('--exp_ver', '--e_v', type=str, default='v1', required=True,
                    help='the version of code, will create subdir in log/ && checkpoints/ ')

parser.add_argument('--train_model', '--t_m', type=str, default='epoch', required=True,
                    choices=['epoch', 'iteration'],
                    help='the version of code, will create subdir in log/ && checkpoints/ ')

parser.add_argument('--feat_type', '--f_t', type=str, default='fc7', required=True, choices=['fc7', 'pool'],
                    help='if using graph head, here should be pool: default(fc7) ')

args = parser.parse_args() 

if __name__ == "__main__":
    data_const = HicoConstants(feat_type=args.feat_type)
    run_model(args, data_const)


