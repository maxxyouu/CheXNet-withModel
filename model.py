# encoding: utf-8

"""
The main CheXNet model implementation.
"""


import os
import numpy as np
import torch
import torch.nn as nn
import torch.backends.cudnn as cudnn
import torchvision
import torchvision.transforms as transforms
from torch.utils.data import DataLoader
from read_data import ChestXrayDataSet
# from sklearn.metrics import roc_auc_score

from modules.densenet import densenet121


CKPT_PATH = 'model.pth.tar'
N_CLASSES = 14
CLASS_NAMES = [ 'Atelectasis', 'Cardiomegaly', 'Effusion', 'Infiltration', 'Mass', 'Nodule', 'Pneumonia',
                'Pneumothorax', 'Consolidation', 'Edema', 'Emphysema', 'Fibrosis', 'Pleural_Thickening', 'Hernia']
DATA_DIR = './ChestX-ray14/images'
# TEST_IMAGE_LIST = './ChestX-ray14/labels/test_list.txt' # NOTE: origin
TEST_IMAGE_LIST = './ChestX-ray14/labels/bbox_list.txt'

BATCH_SIZE = 1

def map_state_dict(checkpoint):
    state_dicts = {}
    for old_key in checkpoint['state_dict']:

        # remove the module. at the begining 
        old_key = old_key.split('module.')[-1]
        old = None
        new = None

        if 'conv.1' in old_key:
            old, new = 'conv.1', 'conv1'
        elif 'conv.2' in old_key:
            old, new = 'conv.2', 'conv2'
        elif 'norm.1' in old_key:
            old, new = 'norm.1', 'norm1'
        elif 'norm.2' in old_key:
            old, new = 'norm.2', 'norm2'

        if old == None or new == None:
            state_dicts[old_key] = checkpoint['state_dict']['module.'+old_key]
        else:
            parts = old_key.split(old)
            new_key = parts[0] + new + parts[-1]        
            state_dicts[new_key] = checkpoint['state_dict']['module.'+old_key]
    
    return state_dicts

def main():

    # cudnn.benchmark = True

    # initialize and load the model
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = DenseNet121(N_CLASSES)
    # model = torch.nn.DataParallel(model)
    if device == 'cuda':
        model = model.cuda()
    

    if os.path.isfile(CKPT_PATH):
        print("=> loading checkpoint")
        checkpoint = torch.load(CKPT_PATH, map_location=device)

        # match the format of the checkpoint dictionary to the state dict of our design
        state_dicts = map_state_dict(checkpoint) 

        model.load_state_dict(state_dicts)
        print("=> loaded checkpoint")
    else:
        print("=> no checkpoint found")

    normalize = transforms.Normalize([0.485, 0.456, 0.406],
                                     [0.229, 0.224, 0.225])

    test_dataset = ChestXrayDataSet(data_dir=DATA_DIR,
                                    image_list_file=TEST_IMAGE_LIST,
                                    transform=transforms.Compose([
                                        transforms.Resize(256),
                                        transforms.TenCrop(224),
                                        transforms.Lambda
                                        (lambda crops: torch.stack([transforms.ToTensor()(crop) for crop in crops])),
                                        transforms.Lambda
                                        (lambda crops: torch.stack([normalize(crop) for crop in crops]))
                                    ]))
    test_loader = DataLoader(dataset=test_dataset, batch_size=BATCH_SIZE,
                             shuffle=False, num_workers=0, pin_memory=False)

    # initialize the ground truth and output tensor
    gt = torch.FloatTensor()
    pred = torch.FloatTensor()

    if device == 'cuda':
        gt = gt.cuda()
        pred = pred.cuda()

    # switch to evaluate mode
    model.eval()

    for i, batch_data in enumerate(test_loader):
        inp, target = batch_data
        if device == 'cuda':
            target = target.cuda()
        gt = torch.cat((gt, target), 0)
        bs, n_crops, c, h, w = inp.size()
        input_var = torch.autograd.Variable(inp.view(-1, c, h, w).cuda() if device == 'cuda' else inp.view(-1, c, h, w))
        output = model(input_var)
        output_mean = output.view(bs, n_crops, -1).mean(1)
        pred = torch.cat((pred, output_mean.data), 0)
        print('hello')

class DenseNet121(nn.Module):
    """Model modified.

    The architecture of our model is the same as standard DenseNet121
    except the classifier layer which has an additional sigmoid function.

    """
    def __init__(self, out_size):
        super(DenseNet121, self).__init__()
        # self.densenet121 = torchvision.models.densenet121(pretrained=True)
        self.densenet121 = densenet121()
        num_ftrs = self.densenet121.classifier.in_features
        self.densenet121.classifier = nn.Sequential(
            nn.Linear(num_ftrs, out_size),
            nn.Sigmoid()
        )

    def forward(self, x):
        x = self.densenet121(x)
        return x


if __name__ == '__main__':
    main()