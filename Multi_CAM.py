import numpy as np
import torch
from torch.autograd import Variable
import torchvision.transforms as transforms
import torchvision.datasets as datasets
from torch.utils.data import DataLoader
from glob import glob
# import imageio
import torch.backends.cudnn as cudnn
from model import DenseNet121, N_CLASSES, map_state_dict, CKPT_PATH, BATCH_SIZE, TEST_IMAGE_LIST, DATA_DIR
import matplotlib.cm
from matplotlib.cm import ScalarMappable
import matplotlib.pyplot as plt
import cv2
from LRP_util import *
import os
import argparse

from read_data import ChestXrayDataSet

# Parse arguments
parser = argparse.ArgumentParser()

parser.add_argument('--models', type=str, default='densenet121',
                    help='resnet50 or vgg16 or vgg19')
parser.add_argument('--target_layer', type=str, default='denseblock4',
                    help='target_layer')
parser.add_argument('--target_class', type=int, default=None,
                    help='target_class')
args = parser.parse_args()

# define data loader

###########################################################################################################################
model_arch = args.models

device = 'cuda' if torch.cuda.is_available() else 'cpu'

model = DenseNet121(N_CLASSES)

print("=> loading checkpoint")
checkpoint = torch.load(CKPT_PATH, map_location=device)
# match the format of the checkpoint dictionary to the state dict of our design
state_dicts = map_state_dict(checkpoint) 
model.load_state_dict(state_dicts)
print("=> loaded checkpoint")

if device == 'cuda':
    model = model.cuda()
model = model.eval()

if args.target_layer == 'denseblock1':
    target_layer = model.densenet121.features.denseblock1
elif args.target_layer == 'denseblock2':
    target_layer = model.densenet121.features.denseblock2
elif args.target_layer == 'denseblock3':
    target_layer = model.densenet121.features.denseblock3
elif args.target_layer == 'denseblock4':
    target_layer = model.densenet121.features.denseblock4

# if model_arch == 'vgg16':
#     model = vgg16_bn(pretrained=True).cuda().eval()  #####
#     target_layer = model.features[int(args.target_layer)]
# elif model_arch == 'vgg19':
#     model = vgg19_bn(pretrained=True).cuda().eval()  #####
#     target_layer = model.features[int(args.target_layer)]
# elif model_arch == 'resnet50':
#     model = resnet50(pretrained=True).cuda().eval() #####
#     if args.target_layer == 'layer1':
#         target_layer = model.layer1
#     elif args.target_layer == 'layer2':
#         target_layer = model.layer2
#     elif args.target_layer == 'layer3':
#         target_layer = model.layer3
#     elif args.target_layer == 'layer4':
#         target_layer = model.layer4
#######################################################################################################################

value = dict()
def forward_hook(module, input, output):
    value['activations'] = output
def backward_hook(module, input, output):
    value['gradients'] = output[0]

target_layer.register_forward_hook(forward_hook)
target_layer.register_backward_hook(backward_hook)

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

for i, batch_data in enumerate(test_loader):
    img_name, inp, target = batch_data
    img_name = img_name[0]
    if device == 'cuda':
        target = target.cuda()
    img = cv2.imread(img_name,1)
    img_show = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img_show = cv2.resize(img_show,(224,224))
    img = np.float32(cv2.resize(img, (224,224)))/255

    # set the target class to be the label
    args.target_class = torch.argmax(target, dim=1)
    # assert(target[args.target_class] == 1)

    in_tensor = preprocess_image(img).cuda() if device == 'cuda' else preprocess_image(img)
    R_CAM, output = model(in_tensor, args.target_layer, [args.target_class], True)

    if args.target_class == None:
        assert('should not happens during evaluation')
        maxindex = np.argmax(output.data.cpu().numpy())
    else:
        maxindex = args.target_class

    # output[:, maxindex].sum().backward(retain_graph=True)
    # activation = value['activations']  # [1, 2048, 7, 7]
    # gradient = value['gradients']  # [1, 2048, 7, 7]
    # gradient_2 = gradient ** 2
    # gradient_3 = gradient ** 3

    # gradient_ = torch.mean(gradient, dim=(2, 3), keepdim=True)
    # grad_cam = activation * gradient_
    # grad_cam = torch.sum(grad_cam, dim=(0, 1))
    # grad_cam = torch.clamp(grad_cam, min=0)
    # grad_cam = grad_cam.data.cpu().numpy() if device == 'cuda' else grad_cam.data.numpy()
    # grad_cam = cv2.resize(grad_cam, (224, 224))


    # alpha_numer = gradient_2
    # alpha_denom = 2 * gradient_2 + torch.sum(activation * gradient_3, axis=(2, 3), keepdims=True)  # + 1e-2
    # alpha = alpha_numer / alpha_denom
    # w = torch.sum(alpha * torch.clamp(gradient, 0), axis=(2, 3), keepdims=True)
    # grad_campp = activation * w
    # grad_campp = torch.sum(grad_campp, dim=(0, 1))
    # grad_campp = torch.clamp(grad_campp, min=0)
    # grad_campp = grad_campp.data.cpu().numpy() if device == 'cuda' else grad_campp.data.numpy()
    # grad_campp = cv2.resize(grad_campp, (224, 224))

    fig = plt.figure(figsize=(10, 10))
    plt.subplots_adjust(bottom=0.01)

    plt.subplot(2, 5, 1)
    plt.imshow(img_show)
    plt.title('Original')
    plt.axis('off')

    plt.subplot(2, 5, 1 + 5)
    plt.imshow(img_show)
    plt.axis('off')

    # plt.subplot(2, 5, 2)
    # plt.imshow((grad_cam),cmap='seismic')
    # plt.imshow(img_show, alpha=.5)
    # plt.title('Grad CAM', fontsize=15)
    # plt.axis('off')

    # plt.subplot(2, 5, 2 + 5)
    # plt.imshow(img_show*threshold(grad_cam)[...,np.newaxis])
    # plt.title('Grad CAM', fontsize=15)
    # plt.axis('off')

    # plt.subplot(2, 5, 3)
    # plt.imshow((grad_campp),cmap='seismic')
    # plt.imshow(img_show, alpha=.5)
    # plt.title('Grad CAM++', fontsize=15)
    # plt.axis('off')

    # plt.subplot(2, 5, 3 + 5)
    # plt.imshow(img_show*threshold(grad_campp)[...,np.newaxis])
    # plt.title('Grad CAM++', fontsize=15)
    # plt.axis('off')

    R_CAM = tensor2image(R_CAM)

    plt.subplot(2, 5, 4)
    plt.imshow((R_CAM),cmap='seismic')
    plt.imshow(img_show, alpha=.5)
    plt.title('Relevance_CAM', fontsize=15)
    plt.axis('off')

    plt.subplot(2, 5, 4 + 5)
    plt.imshow(img_show*threshold(R_CAM)[...,np.newaxis])
    plt.title('Relevance_CAM', fontsize=15)
    plt.axis('off')

    # plt.imshow((R_CAM),cmap='seismic')
    # plt.imshow(img_show, alpha=.5)
    # plt.title('Relevance_CAM - {}'.format(args.target_layer), fontsize=15)
    # plt.axis('off')

    plt.tight_layout()
    plt.draw()
    plt.show()
    plt.clf()
    plt.close()
    

# for path in path_s:
#     img_path_long = './picture/{}'.format(path)
#     img = cv2.imread(img_path_long,1)
#     img_show = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
#     img_show = cv2.resize(img_show,(224,224))
#     img = np.float32(cv2.resize(img, (224,224)))/255

#     in_tensor = preprocess_image(img).cuda() if device == 'cuda' else preprocess_image(img)
#     R_CAM, output = model(in_tensor, args.target_layer, [args.target_class])

#     if args.target_class == None:
#         maxindex = np.argmax(output.data.cpu().numpy())
#     else:
#         maxindex = args.target_class

#     print(index2class[maxindex])
#     save_path = './results/{}_{}'.format(index2class[maxindex][:10], img_path_long.split('/')[-1])

#     output[:, maxindex].sum().backward(retain_graph=True)
#     activation = value['activations']  # [1, 2048, 7, 7]
#     gradient = value['gradients']  # [1, 2048, 7, 7]
#     gradient_2 = gradient ** 2
#     gradient_3 = gradient ** 3

#     gradient_ = torch.mean(gradient, dim=(2, 3), keepdim=True)
#     grad_cam = activation * gradient_
#     grad_cam = torch.sum(grad_cam, dim=(0, 1))
#     grad_cam = torch.clamp(grad_cam, min=0)
#     grad_cam = grad_cam.data.cpu().numpy() if device == 'cuda' else grad_cam.data.numpy()
#     grad_cam = cv2.resize(grad_cam, (224, 224))


#     alpha_numer = gradient_2
#     alpha_denom = 2 * gradient_2 + torch.sum(activation * gradient_3, axis=(2, 3), keepdims=True)  # + 1e-2
#     alpha = alpha_numer / alpha_denom
#     w = torch.sum(alpha * torch.clamp(gradient, 0), axis=(2, 3), keepdims=True)
#     grad_campp = activation * w
#     grad_campp = torch.sum(grad_campp, dim=(0, 1))
#     grad_campp = torch.clamp(grad_campp, min=0)
#     grad_campp = grad_campp.data.cpu().numpy() if device == 'cuda' else grad_campp.data.numpy()
#     grad_campp = cv2.resize(grad_campp, (224, 224))

#     R_CAM = tensor2image(R_CAM)

#     fig = plt.figure(figsize=(10, 10))
#     plt.subplots_adjust(bottom=0.01)

#     plt.subplot(2, 5, 1)
#     plt.imshow(img_show)
#     plt.title('Original')
#     plt.axis('off')

#     plt.subplot(2, 5, 1 + 5)
#     plt.imshow(img_show)
#     plt.axis('off')

#     plt.subplot(2, 5, 2)
#     plt.imshow((grad_cam),cmap='seismic')
#     plt.imshow(img_show, alpha=.5)
#     plt.title('Grad CAM', fontsize=15)
#     plt.axis('off')

#     plt.subplot(2, 5, 2 + 5)
#     plt.imshow(img_show*threshold(grad_cam)[...,np.newaxis])
#     plt.title('Grad CAM', fontsize=15)
#     plt.axis('off')

#     plt.subplot(2, 5, 3)
#     plt.imshow((grad_campp),cmap='seismic')
#     plt.imshow(img_show, alpha=.5)
#     plt.title('Grad CAM++', fontsize=15)
#     plt.axis('off')

#     plt.subplot(2, 5, 3 + 5)
#     plt.imshow(img_show*threshold(grad_campp)[...,np.newaxis])
#     plt.title('Grad CAM++', fontsize=15)
#     plt.axis('off')

#     plt.subplot(2, 5, 4)
#     plt.imshow((R_CAM),cmap='seismic')
#     plt.imshow(img_show, alpha=.5)
#     plt.title('Relevance_CAM', fontsize=15)
#     plt.axis('off')

#     plt.subplot(2, 5, 4 + 5)
#     plt.imshow(img_show*threshold(R_CAM)[...,np.newaxis])
#     plt.title('Relevance_CAM', fontsize=15)
#     plt.axis('off')

#     # plt.subplot(2, 5, 5)
#     # plt.imshow((score_map),cmap='seismic')
#     # plt.imshow(img_show, alpha=.5)
#     # plt.title('XRelevance_CAM', fontsize=15)
#     # plt.axis('off')

#     # plt.subplot(2, 5, 5 + 5)
#     # plt.imshow(img_show*threshold(score_map)[...,np.newaxis])
#     # plt.title('XRelevance_CAM', fontsize=15)
#     # plt.axis('off')

#     plt.tight_layout()
#     plt.draw()
#     # plt.waitforbuttonpress()
#     plt.savefig(save_path)
#     plt.clf()
#     plt.close()

print('Done')